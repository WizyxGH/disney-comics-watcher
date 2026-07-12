import sys
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
from src.config import (
    PARIS_TZ, SKIP_CODIFS, OVERRIDES, GLENAT_KEY_PREFIX, FANTAGRAPHICS_KEY_PREFIX, MARVEL_KEY_PREFIX,
    DYNAMITE_KEY_PREFIX, EGMONT_DE_KEY_PREFIX, KATHIMERINI_KEY_PREFIX, PANINI_IT_KEY_PREFIX, PANINI_BR_KEY_PREFIX,
    NAHDET_MISR_EG_KEY_PREFIX, BG_KEY_PREFIX, HR_KEY_PREFIX, EE_KEY_PREFIX, LV_KEY_PREFIX,
    LT_KEY_PREFIX, PL_KEY_PREFIX, CZ_KEY_PREFIX, RS_KEY_PREFIX, SI_KEY_PREFIX, CN_KEY_PREFIX,
    DK_KEY_PREFIX, ES_KEY_PREFIX, FI_KEY_PREFIX, IS_KEY_PREFIX, NO_KEY_PREFIX, NL_KEY_PREFIX,
    UK_KEY_PREFIX, SE_KEY_PREFIX, LTB_DE_KEY_PREFIX
)
from src.utils import load_state, save_state, parse_date_fr
from src.notifications import notify_magazine, notify_glenat_announce, notify_glenat_release, notify_international_comic

from src.scrapers.fr import discover_fr_kiosk, fetch_fr_kiosk_details, discover_glenat, fetch_glenat_details
from src.scrapers.us import discover_fantagraphics, discover_marvel, discover_dynamite
from src.scrapers.de import discover_egmont_de, fetch_egmont_de_details, discover_lustiges_taschenbuch_de
from src.scrapers.gr import discover_kathimerini
from src.scrapers.it import discover_panini_it, fetch_panini_it_details
from src.scrapers.br import discover_panini_br, fetch_panini_br_details
from src.scrapers.eg import discover_nahdet_misr_eg, fetch_nahdet_misr_eg_details
from src.scrapers.bg import discover_bg, fetch_bg_details
from src.scrapers.hr import discover_hr, fetch_hr_details
from src.scrapers.ee import discover_ee, fetch_ee_details
from src.scrapers.lv import discover_lv, fetch_lv_details
from src.scrapers.lt import discover_lt, fetch_lt_details
from src.scrapers.pl import discover_pl, fetch_pl_details
from src.scrapers.cz import discover_cz, fetch_cz_details
from src.scrapers.rs import discover_rs, fetch_rs_details
from src.scrapers.si import discover_si, fetch_si_details
from src.scrapers.cn import discover_cn, fetch_cn_details
from src.scrapers.dk import discover_dk, fetch_dk_details
from src.scrapers.es import discover_es, fetch_es_details
from src.scrapers.fi import discover_fi, fetch_fi_details
from src.scrapers.isl import discover_is, fetch_is_details
from src.scrapers.no import discover_no, fetch_no_details
from src.scrapers.nl import discover_nl, fetch_nl_details
from src.scrapers.uk import discover_uk, fetch_uk_details
from src.scrapers.se import discover_se, fetch_se_details


def _process_provider_books(
    state: dict, 
    first_run: bool, 
    provider_name: str, 
    key_prefix: str, 
    books: list, 
    country: str,
    default_status: str = "announced",
    fetch_details_func = None,
    is_glenat: bool = False
) -> int:
    notif_count = 0
    print(f"[{provider_name}] Processing {len(books)} comic(s)...")
    today = datetime.now(PARIS_TZ).date()

    for book in books:
        try:
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
                    elif country == "fr_kiosk":
                        notify_magazine(book, releve_date=book.get("releve_date"))
                    else:
                        notify_international_comic(book, state=state, country=country, event_type="release" if target_status == "released" else "announce")
                    notif_count += 1

                state[key] = target_status

        except Exception as e:
            print(f"  [error] Failed to process book {book.get('title')}: {e}")

    return notif_count

def main():
    state = load_state()
    first_run = not state

    notif_count = 0

    PROVIDERS = [
        ("Kiosque FR", "fr_kiosk:", discover_fr_kiosk, "fr_kiosk", "released", fetch_fr_kiosk_details, False),
        ("Glénat", GLENAT_KEY_PREFIX, discover_glenat, "fr", "announced", fetch_glenat_details, True),
        ("Fantagraphics", FANTAGRAPHICS_KEY_PREFIX, discover_fantagraphics, "us", "announced", None, False),
        ("Marvel", MARVEL_KEY_PREFIX, discover_marvel, "us", "announced", None, False),
        ("Dynamite", DYNAMITE_KEY_PREFIX, discover_dynamite, "us", "released", None, False),
        ("Egmont DE", EGMONT_DE_KEY_PREFIX, discover_egmont_de, "de", "released", fetch_egmont_de_details, False),
        ("LTB DE", LTB_DE_KEY_PREFIX, discover_lustiges_taschenbuch_de, "de", "announced", None, False),
        ("Kathimerini GR", KATHIMERINI_KEY_PREFIX, discover_kathimerini, "gr", "released", None, False),
        ("Panini IT", PANINI_IT_KEY_PREFIX, discover_panini_it, "it", "announced", fetch_panini_it_details, False),
        ("Panini BR", PANINI_BR_KEY_PREFIX, discover_panini_br, "br", "announced", fetch_panini_br_details, False),
        ("Nahdet Misr EG", NAHDET_MISR_EG_KEY_PREFIX, discover_nahdet_misr_eg, "eg", "released", fetch_nahdet_misr_eg_details, False),
        ("BG", BG_KEY_PREFIX, discover_bg, "bg", "announced", fetch_bg_details, False),
        ("HR", HR_KEY_PREFIX, discover_hr, "hr", "announced", fetch_hr_details, False),
        ("EE", EE_KEY_PREFIX, discover_ee, "ee", "announced", fetch_ee_details, False),
        ("LV", LV_KEY_PREFIX, discover_lv, "lv", "announced", fetch_lv_details, False),
        ("LT", LT_KEY_PREFIX, discover_lt, "lt", "announced", fetch_lt_details, False),
        ("PL", PL_KEY_PREFIX, discover_pl, "pl", "announced", fetch_pl_details, False),
        ("CZ", CZ_KEY_PREFIX, discover_cz, "cz", "announced", fetch_cz_details, False),
        ("RS", RS_KEY_PREFIX, discover_rs, "rs", "announced", fetch_rs_details, False),
        ("SI", SI_KEY_PREFIX, discover_si, "si", "announced", fetch_si_details, False),
        ("CN", CN_KEY_PREFIX, discover_cn, "cn", "announced", fetch_cn_details, False),
        ("DK", DK_KEY_PREFIX, discover_dk, "dk", "announced", fetch_dk_details, False),
        ("ES", ES_KEY_PREFIX, discover_es, "es", "announced", fetch_es_details, False),
        ("FI", FI_KEY_PREFIX, discover_fi, "fi", "announced", fetch_fi_details, False),
        ("IS", IS_KEY_PREFIX, discover_is, "is", "announced", fetch_is_details, False),
        ("NO", NO_KEY_PREFIX, discover_no, "no", "announced", fetch_no_details, False),
        ("NL", NL_KEY_PREFIX, discover_nl, "nl", "announced", fetch_nl_details, False),
        ("UK", UK_KEY_PREFIX, discover_uk, "uk", "announced", fetch_uk_details, False),
        ("SE", SE_KEY_PREFIX, discover_se, "se", "announced", fetch_se_details, False),
    ]
    
    import concurrent.futures
    print("[Global] Starting parallel discovery for providers...")
    discovered_books = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(PROVIDERS)) as executor:
        future_to_provider = {
            executor.submit(func): (name, prefix, country, default_status, fetch_details, is_glenat)
            for name, prefix, func, country, default_status, fetch_details, is_glenat in PROVIDERS
        }
        for future in concurrent.futures.as_completed(future_to_provider):
            provider_info = future_to_provider[future]
            name = provider_info[0]
            try:
                books = future.result()
                discovered_books[name] = books
            except Exception as e:
                print(f"  [error] discover_{name.lower()}: {e}")
                discovered_books[name] = []

    for name, prefix, func, country, default_status, fetch_details, is_glenat in PROVIDERS:
        books = discovered_books.get(name, [])
        notif_count += _process_provider_books(
            state=state, 
            first_run=first_run, 
            provider_name=name, 
            key_prefix=prefix, 
            books=books, 
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

    import glob
    from src.dbi.cleanup import cleanup_indexed_issues
    cleanup_indexed_issues(glob.glob("issues/*.dbi"))

if __name__ == "__main__":
    main()
