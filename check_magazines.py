import os
from datetime import datetime
from src.config import PARIS_TZ, SKIP_CODIFS, OVERRIDES, GLENAT_KEY_PREFIX
from src.utils import load_state, save_state, parse_date_fr
from src.scrapers import discover_de, discover_mlp_families, discover_glenat, fetch_glenat_details, get_mlp_releve
from src.notifications import notify_magazine, notify_glenat_announce, notify_glenat_release

def main():
    # ── State ─────────────────────────────────────────────────────────────────
    state = load_state()
    first_run = not state
    if first_run:
        print("[init] First run — silent initialization (no notifications).")

    notif_count = 0
    today = datetime.now(PARIS_TZ).date()

    # ── Direct Éditeurs ───────────────────────────────────────────────────────
    print("[DE] Discovering magazines…")
    try:
        magazines = discover_de()
    except Exception as e:
        print(f"  [error] discover_de: {e}")
        magazines = {}
    print(f"  → {len(magazines)} active magazine(s).")

    # ── MLP complementary ────────────────────────────────────────────────────
    print("[MLP] Complementary discovery…")
    try:
        mlp_extra = discover_mlp_families(known_codifs=set(magazines), state=state)
        added = {c: v for c, v in mlp_extra.items() if c not in magazines}
        magazines.update(added)
        print(f"  → +{len(added)} unique MLP codif(s).")
    except Exception as e:
        print(f"  [error] discover_mlp: {e}")

    # ── Magazine processing ───────────────────────────────────────────────────
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

    # ── Glénat ────────────────────────────────────────────────────────────────
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
                    # Retrieve details on-demand before sending the notification
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
                # Retrieve details on-demand before sending the notification
                details = fetch_glenat_details(album["url"])
                album.update(details)
                print(f"  [RELEASE]  {album.get('title', ean)} — Price: {album.get('price') or 'not specified'}")
                notify_glenat_release(album, state=state)
                notif_count += 1
            else:
                print(f"  [RELEASE-SILENT] {album.get('title', ean)}")
            state[key] = "released"

    # ── Saving State ──────────────────────────────────────────────────────────
    save_state(state)

    if first_run:
        print(f"[init] State initialized with {len(state)} entry(ies). Ready for the next run!")
    else:
        print(f"[done] {notif_count} Telegram notification(s) sent.")


if __name__ == "__main__":
    main()
