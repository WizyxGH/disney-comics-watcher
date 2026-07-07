import sys
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
from src.config import PARIS_TZ, SKIP_CODIFS, OVERRIDES, GLENAT_KEY_PREFIX, FANTAGRAPHICS_KEY_PREFIX, MARVEL_KEY_PREFIX, EGMONT_DE_KEY_PREFIX, KATHIMERINI_KEY_PREFIX
from src.utils import load_state, save_state, parse_date_fr
from src.notifications import notify_magazine, notify_glenat_announce, notify_glenat_release, notify_international_comic

# Explicit imports
from src.scrapers.fr import discover_de, discover_mlp_families, get_mlp_releve, discover_glenat, fetch_glenat_details
from src.scrapers.us import discover_fantagraphics, discover_marvel
from src.scrapers.de import discover_egmont_de, fetch_egmont_de_details
from src.scrapers.gr import discover_kathimerini

def process_magazines(state: dict, first_run: bool) -> int:
    notif_count = 0
    print("[DE] Discovering magazines...")
    try:
        magazines = discover_de()
    except Exception as e:
        print(f"  [error] discover_de: {e}")
        magazines = {}
    print(f"  -> {len(magazines)} active magazine(s).")

    print("[MLP] Complementary discovery...")
    try:
        mlp_extra = discover_mlp_families(known_codifs=set(magazines), state=state)
        added = {c: v for c, v in mlp_extra.items() if c not in magazines}
        magazines.update(added)
        print(f"  -> +{len(added)} unique MLP codif(s).")
    except Exception as e:
        print(f"  [error] discover_mlp: {e}")

    for codif, info in magazines.items():
        if codif in SKIP_CODIFS:
            continue
        numero = info.get("numero")
        if not numero:
            continue

        last = state.get(f'magazine:{codif}')
        if last and last.upper().endswith("H"):
            last = last[:-1].strip()
        if numero == last:
            continue  # no change

        ov   = OVERRIDES.get(codif, {})
        name = ov.get("name") or info.get("site_name") or codif
        print(f"  [NEW] {name} - N°{numero}  (previous: {last or '-'})")

        if not first_run:
            releve = info.get("releve_date")
            if not releve:
                try:
                    releve = get_mlp_releve(codif)
                except Exception:
                    pass
            notify_magazine(info, releve_date=releve)
            notif_count += 1

        state[f'magazine:{codif}'] = numero
    return notif_count

def process_provider(
    state: dict, 
    first_run: bool, 
    provider_name: str, 
    key_prefix: str, 
    discover_func, 
    country: str,
    default_status: str = "announced",
    fetch_details_func = None,
    is_glenat: bool = False
) -> int:
    notif_count = 0
    print(f"[{provider_name}] Discovering comics...")
    try:
        books = discover_func()
    except Exception as e:
        print(f"  [error] discover_{provider_name.lower()}: {e}")
        books = []
        
    today = datetime.now(PARIS_TZ).date()

    for book in books:
        book_id = book.get("id") or book.get("sku") or book.get("ean")
        if not book_id: continue
        
        key = f"{key_prefix}{book_id}"
        current = state.get(key)
        
        pub_date = parse_date_fr(book.get("date")) if not book.get("pub_date") else book.get("pub_date")
        is_released = book.get("released", False)
        if pub_date and pub_date <= today:
            is_released = True
        if default_status == "released":
            is_released = True
            
        target_status = "released" if is_released else "announced"

        if current is None or (current == "announced" and target_status == "released"):
            is_indexed = False
            from src.notifications import get_issue_path_from_info
            from src.utils import is_fully_indexed_in_inducks
            
            # Identify path and check indexing to skip heavy fetching
            issue_path = get_issue_path_from_info(book, country)
            if issue_path and issue_path != "unknown":
                is_indexed = is_fully_indexed_in_inducks(issue_path)

            if fetch_details_func and not is_indexed:
                book.update(fetch_details_func(book["url"]))

            silent = False
            if current is None:
                if target_status == "released":
                    silent = (not first_run and default_status != "released") # Wait, if default_status == "released", not first_run -> notify
                    # Actual silent condition in original code: if not first_run and default_status == "released" => notify. else silent.
                    silent = not (not first_run and default_status == "released")
                else:
                    silent = first_run
            else:
                # current == "announced" and target_status == "released"
                silent = first_run

            event_str = "RELEASE" if target_status == "released" else "ANNOUNCE"
            if silent:
                print(f"  [{provider_name}-{event_str}-SILENT] {book.get('title')}")
            else:
                print(f"  [{provider_name}-{event_str}] {book.get('title')}")
                if is_glenat:
                    if target_status == "released":
                        notify_glenat_release(book, state=state)
                    else:
                        notify_glenat_announce(book, state=state)
                else:
                    notify_international_comic(book, state=state, country=country, event_type="release" if target_status == "released" else "announce")
                notif_count += 1
                
            state[key] = target_status

    return notif_count

def main():
    state = load_state()
    first_run = not state

    notif_count = 0

    notif_count += process_magazines(state, first_run)
    
    PROVIDERS = [
        ("Glénat", GLENAT_KEY_PREFIX, discover_glenat, "fr", "announced", fetch_glenat_details, True),
        ("Fantagraphics", FANTAGRAPHICS_KEY_PREFIX, discover_fantagraphics, "us", "announced", None, False),
        ("Marvel", MARVEL_KEY_PREFIX, discover_marvel, "us", "announced", None, False),
        ("Egmont DE", EGMONT_DE_KEY_PREFIX, discover_egmont_de, "de", "released", fetch_egmont_de_details, False),
        ("Kathimerini GR", KATHIMERINI_KEY_PREFIX, discover_kathimerini, "gr", "released", None, False),
    ]
    
    for name, prefix, func, country, default_status, fetch_details, is_glenat in PROVIDERS:
        notif_count += process_provider(
            state=state, 
            first_run=first_run, 
            provider_name=name, 
            key_prefix=prefix, 
            discover_func=func, 
            country=country,
            default_status=default_status,
            fetch_details_func=fetch_details,
            is_glenat=is_glenat
        )

    save_state(state)

    if first_run:
        print(f"[init] State initialized with {len(state)} entry(ies). Ready for the next run!")
    else:
        print(f"[done] {notif_count} Telegram notification(s) sent.")

    from src.dbi.cleanup import cleanup_indexed_issues
    cleanup_indexed_issues(["issues/fr.dbi", "issues/us.dbi", "issues/de.dbi", "issues/gr.dbi"])

if __name__ == "__main__":
    main()
