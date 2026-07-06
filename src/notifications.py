import os
import re
import html as html_lib
import time
import requests
from urllib.parse import quote, quote_plus
from src.config import TELEGRAM_API, TELEGRAM_CHAT_ID, TELEGRAM_THREAD_ID_FR, TELEGRAM_THREAD_ID_US, TELEGRAM_THREAD_ID_DE, TELEGRAM_THREAD_ID_GR, OVERRIDES, AMAZON_AFFILIATE_TAG, SITE_BASE
from src.utils import format_price_fr, get_session, truncate_summary, isbn13_to_isbn10, is_fully_indexed_in_inducks
from src.dbi.generator import generate_dbi_skeleton
from src.dbi.mappers import build_inducks_path
from src.gemini_analyzer import analyze_cover_with_gemini

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
        r = requests.get(url, timeout=15)
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
    for attempt in range(retries):
        try:
            if photo_url:
                payload = {
                    "chat_id":    chat_id,
                    "photo":      photo_url,
                    "caption":    caption,
                    "parse_mode": "HTML",
                }
                if message_thread_id:
                    payload["message_thread_id"] = int(message_thread_id)
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = requests.post(f"{TELEGRAM_API}/sendPhoto", json=payload, timeout=15)
                # Text fallback if image is inaccessible
                if resp.status_code == 400:
                     print(f"  [debug] Telegram 400 error: {resp.text}")
                     desc = resp.json().get("description", "").lower()
                     if any(k in desc for k in ("photo", "wrong url", "failed to get", "url", "web page content")):
                        print(f"  [warn] Photo inaccessible -> fallback to text")
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
                resp = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=15)

            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", delay)
                print(f"  [429] Telegram rate limit — waiting {retry_after}s…")
                time.sleep(retry_after)
                delay = max(delay * 2, retry_after + 1)
                continue

            resp.raise_for_status()
            return resp.json().get("result", {}).get("message_id")

        except requests.RequestException as e:
            print(f"  [error] Telegram (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)

    print("  [FAILURE] Telegram notification not sent.")
    return None


def build_inducks_url(inducks, numero: str) -> str | None:
    """Builds the Inducks URL for a given issue number."""
    path = build_inducks_path(inducks, numero)
    if not path:
        return None
    return f"https://inducks.org/issue.php?c={quote_plus(path)}"




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

def build_glenat_inducks_url(title: str) -> str:
    """Builds the Inducks URL for a Glénat album (direct page if possible, otherwise search)."""
    title_lower = title.lower()
    tome_match = re.search(r'(?:tome|t\.)\s*(\d+)', title_lower)
    tome_num = int(tome_match.group(1)) if tome_match else None

    if "grande histoire de picsou" in title_lower or "grande epopee de picsou" in title_lower or "grande épopée de picsou" in title_lower:
        if tome_num is not None:
            return f"https://inducks.org/issue.php?c={quote_plus(f'fr/GHP{str(tome_num).rjust(4)}')}"
        return "https://inducks.org/publication.php?c=fr/GHP"

    if "ages d'or" in title_lower or "âges d'or" in title_lower or "age d'or" in title_lower or "âge d'or" in title_lower:
        if tome_num is not None:
            return f"https://inducks.org/issue.php?c={quote_plus(f'fr/AOD{str(tome_num).rjust(4)}')}"
        return "https://inducks.org/publication.php?c=fr/AOD"

    return f"https://inducks.org/search.php?search={quote(title)}"

# ── COMMON DISPATCH HELPER ──────────────────────────────────────────────────────

from src.dbi.generator import _RESOLVERS

def get_issue_path_from_info(info: dict, pub_type: str) -> str:
    try:
        from src.config import OVERRIDES
        from src.dbi.mappers import resolve_magazine_metadata, resolve_glenat_metadata
        if pub_type == "magazine":
            data = resolve_magazine_metadata(info, OVERRIDES)
        else:
            resolver = _RESOLVERS.get(pub_type, resolve_glenat_metadata)
            data = resolver(info)
        
        return data.get("issue_path") or ""
    except Exception:
        return "unknown"

def _dispatch_notification(
    info: dict,
    base_caption: str,
    summary: str,
    buttons: list,
    cover_url: str | None,
    message_thread_id: str | None,
    publication_type: str,
    raw_title: str
):
    """Internal helper to dispatch Telegram notification, download cover, and analyze with Gemini."""
# Calculate the official cover_filename
    issue_path = get_issue_path_from_info(info, publication_type)
    issue_code = issue_path.split("/", 1)[-1] if "/" in issue_path else issue_path
    
    m = re.match(r'^([a-zA-Z]+)(\s+)(.*)$', issue_code)
    if m:
        pub_code = m.group(1).lower()
        number = re.sub(r'[^a-zA-Z0-9]', '_', m.group(3)).lower()
        safe_code = f"{pub_code}_{number.zfill(4)}"
    else:
        safe_code = re.sub(r'[^a-zA-Z0-9]', '_', issue_code).lower()
    
    country_prefix = publication_type if publication_type in ("us", "de", "gr") else "fr"
    cover_filename = f"{country_prefix}_{safe_code}a_001"

    # 1. Truncate summary if necessary
    if summary:
        available = 1024 - len(base_caption) - 40
        truncated = truncate_summary(summary, max_len=max(50, available))
        caption = base_caption + f"\n\n<i>{html_lib.escape(truncated)}</i>"
    else:
        caption = base_caption

    # 2. Check if fully indexed
    is_fully_indexed = is_fully_indexed_in_inducks(issue_path)
    
    if is_fully_indexed:
        print(f"  [info] Issue {issue_path} is completely indexed on Inducks. Skipping cover download and DBI generation.")

    # 3. Download cover (only if not fully indexed)
    if cover_url and not is_fully_indexed:
        download_cover(cover_url, cover_filename)

    # 4. Send via Telegram
    if TELEGRAM_CHAT_ID:
        send_telegram(cover_url, caption, buttons=buttons, message_thread_id=message_thread_id)
        time.sleep(1)
    else:
        print("  [warn] No TELEGRAM_CHAT_ID configured.")

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

        # 7. Send DBI to Admin DM
        admin_id = os.environ.get("TELEGRAM_ADMIN_ID")
        if admin_id and dbi_content:
            clean_dbi = html_lib.escape(dbi_content.strip())
            dm_text = f"New DBI generated for <b>{html_lib.escape(raw_title)}</b>:\n<pre>{clean_dbi}</pre>"
            send_telegram(photo_url=None, caption=dm_text, chat_id=admin_id)


# ── PUBLIC NOTIFICATION FUNCTIONS ───────────────────────────────────────────────

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
    if prix: lines.append(f"💶 {html_lib.escape(prix)}")
    if date: lines.append(f"📅 Published: {date}")
    if releve_date: lines.append(f"📅 On newsstands until: {releve_date}")
    
    inducks_url = build_inducks_url(ov.get("inducks"), num) or f"https://inducks.org/search.php?search={quote(f'{name} {num}')}"
    btn_text = "View on MLP" if "mlp.fr" in url.lower() else "View on Direct-éditeurs"
    buttons = [[{"text": btn_text, "url": url}], [{"text": "Contents on Inducks", "url": inducks_url}]]

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
        message_thread_id=TELEGRAM_THREAD_ID_FR,
        publication_type="magazine",
        raw_title=f"{name} {num}"
    )

def _build_glenat_buttons(album: dict, raw_title: str) -> list:
    row1 = [{"text": "View on Glénat", "url": album["url"]}]
    if AMAZON_AFFILIATE_TAG:
        asin = isbn13_to_isbn10(album.get("ean", ""))
        if asin: row1.append({"text": "Buy on Amazon", "url": f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
    return [row1, [{"text": "Contents on Inducks", "url": build_glenat_inducks_url(raw_title)}]]

def notify_glenat_announce(album: dict, state: dict | None = None):
    """Glénat announcement notification (upcoming album)."""
    resolve_dbg_tome_number(album, state)
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    lines = [f"<b>Announcement — {title}</b>", ""]
    if album.get("date"): lines.append(f"🗓 Expected release: {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix: lines.append(f"💶 {html_lib.escape(prix)}")

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=_build_glenat_buttons(album, raw_title),
        cover_url=album.get("cover_url"),
        message_thread_id=TELEGRAM_THREAD_ID_FR,
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
    if prix: lines.append(f"💶 {html_lib.escape(prix)}")

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=_build_glenat_buttons(album, raw_title),
        cover_url=album.get("cover_url"),
        message_thread_id=TELEGRAM_THREAD_ID_FR,
        publication_type="glenat",
        raw_title=raw_title
    )

def notify_international_comic(album: dict, state: dict | None = None, country: str = "us", event_type: str = "announce"):
    """Generic notification function for international releases (US, DE, GR)."""
    title = html_lib.escape(album.get("title", f"{country.upper()} Disney Comic"))
    raw_title = album.get("title", f"{country.upper()} Disney Comic")

    # Format strings based on country and event type
    config = {
        "us": {
            "flag": "🇺🇸",
            "announce_title": f"🇺🇸 <b>Announcement — {title}</b>",
            "release_title": f"<b>{title}</b>",
            "date_prefix": "🗓 Expected publication:" if event_type == "announce" else "🗓 Published on:",
            "price_prefix": "💵 Price:",
            "inducks_btn": "Search on Inducks",
            "thread_id": TELEGRAM_THREAD_ID_US,
        },
        "de": {
            "flag": "🇩🇪",
            "announce_title": f"🇩🇪 <b>Ankündigung — {title}</b>",
            "release_title": f"<b>{title}</b>",
            "date_prefix": "🗓 Geplante Veröffentlichung:" if event_type == "announce" else "🗓 Erschienen am:",
            "price_prefix": "💶 Preis:",
            "inducks_btn": "Auf Inducks suchen",
            "thread_id": TELEGRAM_THREAD_ID_DE,
        },
        "gr": {
            "flag": "🇬🇷",
            "announce_title": f"🇬🇷 <b>Ανακοίνωση — {title}</b>",
            "release_title": f"<b>{title}</b>",
            "date_prefix": "🗓 Αναμενόμενη κυκλοφορία:" if event_type == "announce" else "🗓 Κυκλοφόρησε:",
            "price_prefix": "💶 Τιμή:",
            "inducks_btn": "Στο Inducks",
            "thread_id": TELEGRAM_THREAD_ID_GR,
        }
    }

    cfg = config.get(country, config["us"])
    
    lines = [cfg["announce_title"] if event_type == "announce" else cfg["release_title"], ""]
    if album.get("date"): lines.append(f"{cfg['date_prefix']} {album['date']}")
    if album.get("price"): lines.append(f"{cfg['price_prefix']} {html_lib.escape(album['price'])}")

    row1 = []
    inducks_url = f"https://inducks.org/search.php?search={quote(raw_title)}"

    if country == "us":
        source_name = "Marvel" if album.get("source") == "marvel" else "Fantagraphics"
        row1.append({"text": f"View on {source_name}", "url": album.get("url", "")})
        if AMAZON_AFFILIATE_TAG and album.get("sku"):
            asin = isbn13_to_isbn10(album.get("sku", ""))
            if asin: row1.append({"text": "Buy on Amazon", "url": f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
    elif country == "de":
        row1.append({"text": "Auf Egmont-Shop ansehen", "url": album.get("url", "")})
    elif country == "gr":
        row1.append({"text": "Διαβάστε στην Καθημερινή", "url": album.get("url", "")})
        # Try to parse Greek title to Inducks code
        inducks_code = None
        search_query = quote(raw_title)
        if "Μίκυ Μάους" in raw_title:
            m = re.search(r'#(\d+)', raw_title)
            if m: inducks_code = f"gr/MM {m.group(1)}"
        elif "Ντόναλντ" in raw_title:
            m = re.search(r'#(\d+)', raw_title)
            if m: inducks_code = f"gr/DD {m.group(1)}"
        elif "Super MIKY" in raw_title:
            m = re.search(r'#(\d+)', raw_title)
            if m: inducks_code = f"gr/SM {m.group(1)}"
        elif "Κόμιξ" in raw_title or "ΚΟΜΙΞ" in raw_title:
            m = re.search(r'#(\d+)', raw_title)
            if m: inducks_code = f"gr/KX {m.group(1)}"
        
        if inducks_code:
            inducks_url = f"https://inducks.org/issue.php?c={quote_plus(inducks_code)}"
        else:
            inducks_url = f"https://inducks.org/search.php?search={search_query}"

    buttons = [row1, [{"text": cfg["inducks_btn"], "url": inducks_url}]] if row1 else [[{"text": cfg["inducks_btn"], "url": inducks_url}]]

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=buttons,
        cover_url=album.get("cover_url"),
        message_thread_id=cfg["thread_id"],
        publication_type=country,
        raw_title=raw_title
    )


