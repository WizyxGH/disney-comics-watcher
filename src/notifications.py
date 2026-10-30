import os
import re
import html as html_lib
import time
import requests
from urllib.parse import quote_plus, urlencode
from src.config import (
    TELEGRAM_API, TELEGRAM_CHAT_ID, TELEGRAM_THREADS,
    DISCORD_ADMIN_WEBHOOK_URL, NOTIFY_BACKENDS,
    OVERRIDES, SITE_BASE, SUPPORTED_COUNTRIES,
)
from src.discord import send_discord, role_mention, build_link_line, html_to_markdown
from src.utils import format_price_fr, get_session, truncate_summary, is_fully_indexed_in_inducks, does_issue_exist_in_inducks, cover_filename
from src.dbi.generator import generate_dbi_skeleton
from src.dbi.mappers import resolve_magazine_metadata, resolve_glenat_metadata, resolve_comic_metadata
from src.dbi.isv_search import _extract_base_and_number
from src.gemini_analyzer import analyze_cover_with_gemini

# One pooled connection to api.telegram.org, mirroring the one in src/discord.py.
_tg_session = requests.Session()


def resolve_dbg_tome_number(album: dict, state: dict | None = None):
    """Resolves and extrapolates the next issue number for Disney By Glénat (DBG) albums."""
    if album.get("numero_de_tome") is None:
        pass



def download_cover(url: str | None, filename: str):
    """Downloads and saves the cover image to the 'covers' directory."""
    if not url:
        return
    os.makedirs("covers", exist_ok=True)
    
    # Make filename safe
    filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).strip()
    filename = filename.replace(' ', '_')
    if not filename.lower().endswith('.jpg') and not filename.lower().endswith('.jpeg') and not filename.lower().endswith('.png'):
        filename += ".jpg"
        
    filepath = os.path.join("covers", filename)
    if os.path.exists(filepath):
        return
        
    try:
        r = get_session().get(url, timeout=15)
        r.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(r.content)
        print(f"  [info] Cover saved: {filepath}")
    except Exception as e:
        print(f"  [warn] Failed to download cover {url}: {e}")


def send_telegram(photo_url: str | None, caption: str, buttons: list | None = None, retries: int = 5, chat_id: str = TELEGRAM_CHAT_ID, message_thread_id: str | None = None):
    """Sends a Telegram message with a photo (sendPhoto) or text only (sendMessage).
    Automatically handles rate limits (429) and inaccessible photos.
    buttons: list of button rows, e.g. [[{"text": "Voir", "url": "..."}]]
    Returns the Telegram message_id (int) if successful, None otherwise."""
    delay = 2
    reply_markup = {"inline_keyboard": buttons} if buttons else None

    # Telegram sendPhoto caption limit is 1024 characters. Fall back to sendMessage if exceeded.
    if photo_url and len(caption) > 1024:
        photo_url = None

    for attempt in range(retries):
        try:
            if photo_url:
                payload = {
                    "chat_id":    chat_id,
                    "photo":      photo_url,
                    "caption":    caption[:1024],
                    "parse_mode": "HTML",
                }
                if message_thread_id:
                    payload["message_thread_id"] = int(message_thread_id)
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = _tg_session.post(f"{TELEGRAM_API}/sendPhoto", json=payload, timeout=15)
                # Text fallback if image is inaccessible or caption is too long
                if resp.status_code == 400:
                     print(f"  [debug] Telegram 400 error: {resp.text}")
                     desc = resp.json().get("description", "").lower()
                     if any(k in desc for k in ("photo", "wrong url", "failed to get", "url", "web page content", "caption is too long", "caption too long")):
                        print(f"  [warn] Photo/caption issue ({desc}) -> fallback to text")
                        photo_url = None
                        continue
            else:
                payload = {
                    "chat_id":                  chat_id,
                    "text":                     caption[:4096],
                    "parse_mode":               "HTML",
                    "disable_web_page_preview": True,
                }
                if message_thread_id:
                    payload["message_thread_id"] = int(message_thread_id)
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = _tg_session.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=15)

            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", delay)
                print(f"  [429] Telegram rate limit — waiting {retry_after}s…")
                time.sleep(retry_after)
                delay = max(delay * 2, retry_after + 1)
                continue

            if 400 <= resp.status_code < 500:
                # The request itself is wrong (bad chat, bad HTML…): sending it
                # again five times only delays the run and the next messages.
                print(f"  [error] Telegram {resp.status_code}, not retried: {resp.text[:300]}")
                return None

            resp.raise_for_status()
            return resp.json().get("result", {}).get("message_id")

        except requests.RequestException as e:
            print(f"  [error] Telegram (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)

    print("  [FAILURE] Telegram notification not sent.")
    return None


INDUCKS_BUTTONS = ("Search on Inducks", "Search Inducks", "View on Inducks", "View Publication", "View issues")


def inducks_button(issue_path: str | None, raw_title: str, country: str, info: dict | None = None) -> dict:
    """The Inducks button of a release: the issue page when Inducks lists the
    issue, otherwise Inducks' advanced search (comp.php?mode=2) filled with
    what is known, as precise as it gets: country, publication (or title),
    number, year. A not-yet-indexed issue has no page: issue.php would only
    say "not found", while the search finds it as soon as Inducks adds it.
    The publisher keeps out homonyms of other houses (it/PK 119 is Disney
    Italia's, Panini's Paperinik 119 is it/PPK)."""
    info = info or {}
    known = bool(issue_path) and "UNK" not in issue_path and "/" in issue_path
    if known and not re.search(r"\d", issue_path):
        # Only the publication is known.
        return {"text": "View issues", "url": f"https://inducks.org/publication.php?c={quote_plus(issue_path)}"}
    if known and does_issue_exist_in_inducks(issue_path):
        return {"text": "View on Inducks", "url": f"https://inducks.org/issue.php?c={quote_plus(issue_path)}"}

    params = {"country": country}
    if known:
        # 'it/PM  557' -> publication 'PM' (the search reads entry codes), number '557'.
        pub, _, number = issue_path.split("/", 1)[1].rpartition(" ")
        if not pub:
            pub, number = re.match(r"^([A-Za-z]+)(.*)$", issue_path.split("/", 1)[1]).groups()
        params["title1"], params["entrycodeh3"] = pub.strip(), number.strip()
    else:
        base, number = _extract_base_and_number(raw_title or "")
        params["title1"] = base or raw_title or ""
        if number:
            params["entrycodeh3"] = number
    year = re.search(r"\b(19|20)\d{2}\b", str(info.get("date") or info.get("date_mise_en_vente") or ""))
    if year:
        # "equal to or after": a new release keeps old homonyms out.
        params["date2"] = year.group(0)
    params["publisher"] = info.get("publisher") or info.get("editeur") or info.get("editor")
    return {"text": "Search on Inducks", "url": "https://inducks.org/compmag.php?" + urlencode({k: v for k, v in params.items() if v})}





def fetch_disneymagazines_cover(slug: str) -> str | None:
    """Attempts to retrieve a higher quality cover image from disneymagazines.fr."""
    if not slug:
        return None
    url = f"https://www.disneymagazines.fr/titre/{slug}"
    try:
        s = get_session()
        r = s.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            timeout=10
        )
        if r.status_code == 200:
            m = re.search(r'"(https://fleuruspresse-disney\.twic\.pics/media/[^"]+\.jpg)[^"]*"', r.text)
            if m: return m.group(1)
            m = re.search(r'"(https://www\.disneymagazines\.fr/media/cache/[^"]+\.jpg)"', r.text)
            if m: return m.group(1)
            m = re.search(r'src="(/media/image/[^"]+\.jpg)"', r.text)
            if m: return f"https://www.disneymagazines.fr{m.group(1)}"
    except Exception as e:
        print(f"  [warn] Unable to retrieve cover from DisneyMagazines for {slug}: {e}")
    return None

# ── COMMON DISPATCH HELPER ──────────────────────────────────────────────────────

from src.dbi.generator import _RESOLVERS

def get_issue_path_from_info(info: dict, pub_type: str) -> str:
    try:
        if pub_type in ("magazine", "fr_kiosk"):
            data = resolve_magazine_metadata(info, OVERRIDES)
        elif pub_type == "glenat":
            data = resolve_glenat_metadata(info)
        elif pub_type in SUPPORTED_COUNTRIES:
            data = resolve_comic_metadata(info, pub_type)
        else:
            data = resolve_glenat_metadata(info)
        
        return data.get("issue_path") or ""
    except Exception:
        return "unknown"

def _is_placeholder_cover(url: str | None) -> bool:
    """Returns True if the cover URL is a known placeholder / 'coming soon' image."""
    if not url:
        return True
    url_lower = url.lower()
    return any(p in url_lower for p in (
        'placeholder/default/', 'placeholder_1.jpg', 'placeholder.jpg',
        'coming-soon', 'coming_soon', 'comingsoon', 'no-image', 'no_image',
        'coverabbildung-nicht-verfugbar',
    ))

def _dispatch_notification(
    info: dict,
    base_caption: str,
    summary: str,
    buttons: list,
    cover_url: str | None,
    publication_type: str,
    raw_title: str
):
    """Internal helper to dispatch the notification to the enabled backends,
    download the cover, and analyze it with Gemini."""
    # Nullify placeholder / "coming soon" covers so they aren't sent
    if _is_placeholder_cover(cover_url):
        cover_url = None

# Calculate the official cover_filename
    issue_path = get_issue_path_from_info(info, publication_type)
    issue_code = issue_path.split("/", 1)[-1] if "/" in issue_path else issue_path

    # 'magazine' and 'glenat' are French publication types; the others are country codes.
    country = publication_type if publication_type in SUPPORTED_COUNTRIES else "fr"
    cover_name = cover_filename(issue_code, country)

    # 1. Truncate summary if necessary
    if summary:
        available = 1024 - len(base_caption) - 40
        if available > 50:
            truncated = truncate_summary(summary, max_len=available)
            caption = base_caption + f"\n\n<i>{html_lib.escape(truncated)}</i>"
        else:
            caption = base_caption
    else:
        caption = base_caption

    # 2. Check if fully indexed
    is_fully_indexed = is_fully_indexed_in_inducks(issue_path)
    
    if is_fully_indexed:
        print(f"  [info] Issue {issue_path} is completely indexed on Inducks. Skipping cover download and DBI generation.")

    # 3. Download cover (only if not fully indexed)
    if cover_url and not is_fully_indexed:
        download_cover(cover_url, cover_name)

    # 4. Process buttons dynamically based on Inducks
    final_buttons = []
    if buttons:
        for row in buttons:
            new_row = []
            for btn in row:
                if btn.get("text") in INDUCKS_BUTTONS:
                    new_row.append(inducks_button(issue_path, raw_title, country, info))
                else:
                    new_row.append(btn)
            final_buttons.append(new_row)

    # 5. Send to the enabled backends
    if "telegram" in NOTIFY_BACKENDS:
        if TELEGRAM_CHAT_ID:
            send_telegram(cover_url, caption, buttons=final_buttons,
                          message_thread_id=TELEGRAM_THREADS.get(country))
            time.sleep(1)
        else:
            print("  [warn] No TELEGRAM_CHAT_ID configured.")

    if "discord" in NOTIFY_BACKENDS:
        description = html_to_markdown(caption)
        link_line = build_link_line(final_buttons)
        if link_line:
            description += f"\n\n{link_line}"
        send_discord(
            text=description,
            image_url=cover_url,
            mention=role_mention(country),
        )
        time.sleep(1)

    # 5. Gemini Cover Analysis (only if not fully indexed)
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and cover_url and not is_fully_indexed:
        print(f"  [Gemini] Analyzing cover for '{raw_title}'...")
        analysis = analyze_cover_with_gemini(cover_url, api_key)
        
        if publication_type in ("magazine", "de"):
            cover_title = analysis.get("title")
            if cover_title:
                print(f"  [Gemini] Extracted title: '{cover_title}'")
                info["cover_title"] = cover_title
        
        characters = analysis.get("characters", [])
        if characters:
            char_list = ", ".join(f"{c['name_fr']} ({c['code']})" if c.get('code') else c['name_fr'] for c in characters)
            print(f"  [Gemini] Detected characters: {char_list}")
            info["characters"] = characters

    # 6. Generate DBI skeleton (only if not fully indexed)
    if not is_fully_indexed:
        dbi_content = generate_dbi_skeleton(info, publication_type=publication_type, overrides=OVERRIDES)

        # 7. Send DBI to the admin channel / DM
        if dbi_content:
            # Remove ^^ Source: line for the message
            dbi_lines = [line for line in dbi_content.strip().split("\n") if not line.startswith("^^ Source")]
            clean_dbi = html_lib.escape("\n".join(dbi_lines).strip())

            source_url = info.get("url")
            title_html = f'<a href="{html_lib.escape(source_url)}"><b>{html_lib.escape(raw_title)}</b></a>' if source_url else f'<b>{html_lib.escape(raw_title)}</b>'
            dm_text = f"New DBI generated for {title_html}:\n<pre>{clean_dbi}</pre>"
            
            dm_buttons = None
            if issue_path and "UNK" not in issue_path:
                # sendscan.php for Bolderbast server (e.g. c=de&s=LTBYC&i=LTB+YC+22&u=LTB+YC+22a)
                country_part = issue_path.split("/", 1)[0]
                issue_part = issue_path.split("/", 1)[1] if "/" in issue_path else issue_path
                s_part = quote_plus(issue_part.split(" ")[0] if " " in issue_part else issue_part)
                i_part = quote_plus(issue_part)
                u_part = f"{i_part}a"
                upload_url = f"https://inducks.org/sendscan.php?c={quote_plus(country_part)}&s={s_part}&i={i_part}&u={u_part}"
                
                dm_buttons = [[{"text": "Upload Scan", "url": upload_url}]]

            send_admin(dm_text, photo_url=cover_url, buttons=dm_buttons)


# ── PUBLIC NOTIFICATION FUNCTIONS ───────────────────────────────────────────────

def send_admin(text_html: str, photo_url: str | None = None, buttons: list | None = None):
    """Sends a message to the admin DM (Telegram) and admin channel (Discord):
    DBI skeletons, and the watcher's own alerts about sources gone silent."""
    admin_id = os.environ.get("TELEGRAM_ADMIN_ID")
    if "telegram" in NOTIFY_BACKENDS and admin_id:
        # Sent as text past the caption limit (a DBI in <pre> is long).
        send_telegram(photo_url=photo_url if len(text_html) <= 1024 else None,
                      caption=text_html, chat_id=admin_id, buttons=buttons)

    if "discord" in NOTIFY_BACKENDS and DISCORD_ADMIN_WEBHOOK_URL:
        description = html_to_markdown(text_html)
        links = build_link_line(buttons)
        if links:
            description += f"\n\n{links}"
        send_discord(text=description, image_url=photo_url, webhook_url=DISCORD_ADMIN_WEBHOOK_URL)


def notify_magazine(info: dict, releve_date: str | None = None):
    """Sends the Telegram notification for a new magazine issue."""
    codif = info["codif"]
    ov    = OVERRIDES.get(codif, {})
    name  = ov.get("name") or info.get("site_name") or info.get("slug") or codif
    num   = info.get("numero", "?")
    prix  = format_price_fr(info.get("prix"))
    date  = info.get("date_mise_en_vente")
    url   = info.get("url", SITE_BASE)

    title_line = f"<b>{html_lib.escape(name)} {num}</b>"
    lines = [title_line, ""]
    if prix: lines.append(f"💶 Price: {html_lib.escape(prix)}")
    if date: lines.append(f"📅 Published: {date}")
    if releve_date: lines.append(f"📅 On newsstands until: {releve_date}")
    
    # The Inducks button is filled in by _dispatch_notification.
    buttons = [[{"text": "View Source", "url": url}], [{"text": "Search on Inducks", "url": ""}]]

    cover_url = None
    if info.get("slug"):
        cover_url = fetch_disneymagazines_cover(info.get("slug"))
        if cover_url: print(f"  [info] High quality cover found on DisneyMagazines: {cover_url}")
    if not cover_url:
        cover_url = info.get("cover_url")

    inducks_val = ov.get("inducks")
    pub_code = codif
    if isinstance(inducks_val, str):
        pub_code = inducks_val
    elif isinstance(inducks_val, tuple) and len(inducks_val) > 0:
        pub_code = inducks_val[0]
        if pub_code == "JMHSN": pub_code = "JMHS"
    
    import re
    clean_num = re.sub(r'[^0-9A-Za-z]', '', str(num))
    cover_fn = f"fr_{pub_code}_{clean_num}"

    _dispatch_notification(
        info=info,
        base_caption="\n".join(lines),
        summary="",
        buttons=buttons,
        cover_url=cover_url,
        publication_type="magazine",
        raw_title=f"{name} {num}"
    )

def _build_glenat_buttons(album: dict, raw_title: str) -> list:
    row1 = [{"text": "View Source", "url": album["url"]}]
    # The Inducks button is filled in by _dispatch_notification.
    return [row1, [{"text": "Search on Inducks", "url": ""}]]

def notify_glenat_announce(album: dict, state: dict | None = None):
    """Glénat announcement notification (upcoming album)."""
    resolve_dbg_tome_number(album, state)
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    lines = [f"<b>Announcement — {title}</b>", ""]
    if album.get("date"): lines.append(f"🗓 Expected release: {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix: lines.append(f"💶 Price: {html_lib.escape(prix)}")

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=_build_glenat_buttons(album, raw_title),
        cover_url=album.get("cover_url"),
        publication_type="glenat",
        raw_title=raw_title
    )

def notify_glenat_release(album: dict, state: dict | None = None):
    """Glénat release notification (album available in bookstores)."""
    resolve_dbg_tome_number(album, state)
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    lines = [f"<b>{title}</b>", ""]
    if album.get("date"): lines.append(f"🗓 Released: {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix: lines.append(f"💶 Price: {html_lib.escape(prix)}")

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=_build_glenat_buttons(album, raw_title),
        cover_url=album.get("cover_url"),
        publication_type="glenat",
        raw_title=raw_title
    )

def notify_international_comic(album: dict, state: dict | None = None, country: str = "us", event_type: str = "announce"):
    """Generic notification function for international releases (US, DE, GR)."""
    title = html_lib.escape(album.get("title", f"{country.upper()} Disney Comic"))
    raw_title = album.get("title", f"{country.upper()} Disney Comic")

    # Only the price symbol varies per country; everything else is shared.
    PRICE_PREFIX = {
        "us": "💵 Price:", "br": "💵 Price:", "eg": "EGP Price:",
        "de": "💶 Price:", "gr": "💶 Price:", "it": "💶 Price:",
    }
    date_prefix  = "🗓 Expected release:" if event_type == "announce" else "🗓 Released:"
    price_prefix = PRICE_PREFIX.get(country, "Price:")

    lines = [f"<b>Announcement — {title}</b>" if event_type == "announce" else f"<b>{title}</b>", ""]
    if album.get("date"): lines.append(f"{date_prefix} {album['date']}")
    if album.get("price"): lines.append(f"{price_prefix} {html_lib.escape(album['price'])}")

    # The Inducks button is filled in by _dispatch_notification.
    buttons = [[{"text": "View Source", "url": album.get("url", "")}], [{"text": "Search on Inducks", "url": ""}]]

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=buttons,
        cover_url=album.get("cover_url"),
        publication_type=country,
        raw_title=raw_title
    )


