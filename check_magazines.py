import os
from datetime import datetime
from src.config import PARIS_TZ, SKIP_CODIFS, OVERRIDES, GLENAT_KEY_PREFIX, FANTAGRAPHICS_KEY_PREFIX, MARVEL_KEY_PREFIX
from src.utils import load_state, save_state, parse_date_fr
from src.scrapers import discover_de, discover_mlp_families, discover_glenat, fetch_glenat_details, get_mlp_releve, discover_fantagraphics, discover_marvel
from src.notifications import notify_magazine, notify_glenat_announce, notify_glenat_release, notify_us_release

def process_magazines(state: dict, first_run: bool) -> int:
    notif_count = 0
    print("[DE] Discovering magazines…")
    try:
        magazines = discover_de()
    except Exception as e:
        print(f"  [error] discover_de: {e}")
        magazines = {}
    print(f"  → {len(magazines)} active magazine(s).")

    print("[MLP] Complementary discovery…")
    try:
        mlp_extra = discover_mlp_families(known_codifs=set(magazines), state=state)
        added = {c: v for c, v in mlp_extra.items() if c not in magazines}
        magazines.update(added)
        print(f"  → +{len(added)} unique MLP codif(s).")
    except Exception as e:
        print(f"  [error] discover_mlp: {e}")

    for codif, info in magazines.items():
        if codif in SKIP_CODIFS:
            continue
        numero = info.get("numero")
        if not numero:
            continue

        last = state.get(codif)
        if last and last.upper().endswith("H"):
            last = last[:-1].strip()
        if numero == last:
            continue  # no change

        ov   = OVERRIDES.get(codif, {})
        name = ov.get("name") or info.get("site_name") or codif
        print(f"  [NEW] {name} — N°{numero}  (previous: {last or '—'})")

        if not first_run:
            releve = info.get("releve_date")
            if not releve:
                try:
                    releve = get_mlp_releve(codif)
                except Exception:
                    pass
            notify_magazine(info, releve_date=releve)
            notif_count += 1

        state[codif] = numero
    return notif_count

def process_glenat(state: dict, first_run: bool, today) -> int:
    notif_count = 0
    print("[Glénat] Discovering Disney comic books…")
    try:
        glenat_albums = discover_glenat()
        print(f"  → {len(glenat_albums)} album(s) found.")
    except Exception as e:
        print(f"  [error] discover_glenat: {e}")
        glenat_albums = []

    for album in glenat_albums:
        ean = album.get("ean")
        if not ean:
            continue
        key     = f"{GLENAT_KEY_PREFIX}{ean}"
        current = state.get(key)
        pub_date = album.get("pub_date")

        if current is None:
            # New album detected
            if pub_date and pub_date <= today:
                # Already released in the past -> we record it directly as released without notifying
                print(f"  [RELEASE-SILENT-INIT] {album.get('title', ean)}")
                state[key] = "released"
            else:
                # Upcoming album -> announcement notification
                if not first_run:
                    details = fetch_glenat_details(album["url"])
                    album.update(details)
                    print(f"  [ANNOUNCEMENT] {album.get('title', ean)} — Price: {album.get('price') or 'not specified'}")
                    notify_glenat_announce(album, state=state)
                    notif_count += 1
                else:
                    print(f"  [ANNOUNCEMENT-SILENT] {album.get('title', ean)}")
                state[key] = "announced"

        elif current == "announced" and pub_date and pub_date <= today:
            # Announced album whose publication date is reached → release in bookstores
            if not first_run:
                details = fetch_glenat_details(album["url"])
                album.update(details)
                print(f"  [RELEASE]  {album.get('title', ean)} — Price: {album.get('price') or 'not specified'}")
                notify_glenat_release(album, state=state)
                notif_count += 1
            else:
                print(f"  [RELEASE-SILENT] {album.get('title', ean)}")
            state[key] = "released"
    return notif_count

def process_fantagraphics(state: dict, first_run: bool) -> int:
    notif_count = 0
    print("[Fantagraphics] Discovering US Disney comic books…")
    try:
        fanta_books = discover_fantagraphics()
        print(f"  → {len(fanta_books)} US book(s) found.")
    except Exception as e:
        print(f"  [error] discover_fantagraphics: {e}")
        fanta_books = []

    today = datetime.now(PARIS_TZ).date()

    for book in fanta_books:
        book_id = book.get("id")
        if not book_id:
            continue
        key = f"{FANTAGRAPHICS_KEY_PREFIX}{book_id}"
        current = state.get(key)
        
        if current is None:
            pub_date_str = book.get("date")
            pub_date = parse_date_fr(pub_date_str) if pub_date_str else None
            
            if pub_date and pub_date <= today:
                print(f"  [US-RELEASE-SILENT-INIT] {book.get('title')}")
                state[key] = "released"
            else:
                if first_run:
                    print(f"  [US-RELEASE-SILENT-INIT] {book.get('title')}")
                else:
                    print(f"  [US-RELEASE] {book.get('title')} — Price: {book.get('price') or 'not specified'}")
                    notify_us_release(book, state=state)
                    notif_count += 1
                state[key] = "released"
    return notif_count

def process_marvel(state: dict, first_run: bool) -> int:
    notif_count = 0
    print("[Marvel] Discovering US Disney comic books…")
    try:
        marvel_books = discover_marvel()
        print(f"  → {len(marvel_books)} US book(s) found.")
    except Exception as e:
        print(f"  [error] discover_marvel: {e}")
        marvel_books = []

    today = datetime.now(PARIS_TZ).date()

    for book in marvel_books:
        book_id = book.get("id")
        if not book_id:
            continue
        key = f"{MARVEL_KEY_PREFIX}{book_id}"
        current = state.get(key)
        
        if current is None:
            pub_date_str = book.get("date")
            pub_date = parse_date_fr(pub_date_str) if pub_date_str else None
            
            if pub_date and pub_date <= today:
                print(f"  [US-RELEASE-SILENT-INIT] {book.get('title')}")
                state[key] = "released"
            else:
                if first_run:
                    print(f"  [US-RELEASE-SILENT-INIT] {book.get('title')}")
                else:
                    print(f"  [US-RELEASE] {book.get('title')} — Price: {book.get('price') or 'not specified'}")
                    notify_us_release(book, state=state)
                    notif_count += 1
                state[key] = "released"
    return notif_count

def main():
    state = load_state()
    first_run = not state
    if first_run:
        print("[init] First run — silent initialization (no notifications).")

    today = datetime.now(PARIS_TZ).date()
    notif_count = 0

    notif_count += process_magazines(state, first_run)
    notif_count += process_glenat(state, first_run, today)
    notif_count += process_fantagraphics(state, first_run)
    notif_count += process_marvel(state, first_run)

    save_state(state)

    if first_run:
        print(f"[init] State initialized with {len(state)} entry(ies). Ready for the next run!")
    else:
        print(f"[done] {notif_count} Telegram notification(s) sent.")

if __name__ == "__main__":
    main()
