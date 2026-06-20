import os
import re
import html as html_lib
import time
import requests
from urllib.parse import quote, quote_plus
from src.config import TELEGRAM_API, TELEGRAM_CHAT_ID, TELEGRAM_THREAD_ID_FR, TELEGRAM_THREAD_ID_US, OVERRIDES, AMAZON_AFFILIATE_TAG, SITE_BASE
from src.utils import format_price_fr, get_session, load_state, save_state
from src.scrapers import get_latest_inducks_issue_number
from src.dbi_generator import generate_dbi_skeleton, build_inducks_path
from src.gemini_analyzer import analyze_cover_with_gemini

def resolve_dbg_tome_number(album: dict, state: dict | None = None):
    """Resolves and extrapolates the next issue number for Disney By Glénat (DBG) albums."""
    if album.get("numero_de_tome") is None:
        coll = album.get("collection_label")
        ser = album.get("serie_label")


def truncate_summary(text: str, max_len: int = 400) -> str:
    """Cleanly truncates the summary to avoid cutting a word in half."""
    if not text or len(text) <= max_len:
        return text or ""
    truncated = text[:max_len]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.strip() + "…"


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
        print(f"  [info] Couverture sauvegardée : {filepath}")
    except Exception as e:
        print(f"  [warn] Impossible de télécharger la couverture {url}: {e}")


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
                     if any(k in desc for k in ("photo", "wrong url", "failed to get", "url")):
                        print(f"  [warn] Photo inaccessible → fallback to text")
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


def isbn13_to_isbn10(isbn13: str) -> str | None:
    """Converts an ISBN-13 (starting with 978) to an ISBN-10 (Amazon ASIN)."""
    clean = "".join(filter(str.isdigit, isbn13))
    if len(clean) != 13 or not clean.startswith("978"):
        return None
    
    digits = clean[3:12]
    
    total = sum(int(digit) * (10 - i) for i, digit in enumerate(digits))
    rem = total % 11
    check = 11 - rem
    if check == 10:
        check_char = "X"
    elif check == 11:
        check_char = "0"
    else:
        check_char = str(check)
        
    return digits + check_char


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

def _dispatch_notification(
    info: dict,
    base_caption: str,
    summary: str,
    buttons: list,
    cover_url: str | None,
    cover_filename: str,
    message_thread_id: str | None,
    publication_type: str,
    raw_title: str
):
    """Internal helper to dispatch Telegram notification, download cover, and analyze with Gemini."""
    # 1. Truncate summary if necessary
    if summary:
        available = 1024 - len(base_caption) - 40
        truncated = truncate_summary(summary, max_len=max(50, available))
        caption = base_caption + f"\n\n<i>{html_lib.escape(truncated)}</i>"
    else:
        caption = base_caption

    # 2. Download cover
    if cover_url:
        download_cover(cover_url, cover_filename)

    # 3. Send via Telegram
    if TELEGRAM_CHAT_ID:
        send_telegram(cover_url, caption, buttons=buttons, message_thread_id=message_thread_id)
        time.sleep(1)
    else:
        print("  [warn] No TELEGRAM_CHAT_ID configured.")

    # 4. Gemini Cover Analysis
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and cover_url:
        print(f"  [Gemini] Analyzing cover for '{raw_title}'...")
        analysis = analyze_cover_with_gemini(cover_url, api_key)
        
        if publication_type == "magazine":
            cover_title = analysis.get("title")
            if cover_title:
                print(f"  [Gemini] Extracted title: '{cover_title}'")
                info["cover_title"] = cover_title
        
        characters = analysis.get("characters", [])
        if characters:
            char_list = ", ".join(f"{c['name_fr']} ({c['code']})" if c.get('code') else c['name_fr'] for c in characters)
            print(f"  [Gemini] Detected characters: {char_list}")
            info["characters"] = characters

    # 5. Generate DBI skeleton
    generate_dbi_skeleton(info, publication_type=publication_type, overrides=OVERRIDES)

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
    if date: lines.append(f"📅 Paru le : {date}")
    if releve_date: lines.append(f"📅 En kiosque jusqu'au : {releve_date}")
    
    inducks_url = build_inducks_url(ov.get("inducks"), num) or f"https://inducks.org/search.php?search={quote(f'{name} {num}')}"
    btn_text = "Voir sur MLP" if "mlp.fr" in url.lower() else "Voir sur Direct-éditeurs"
    buttons = [[{"text": btn_text, "url": url}], [{"text": "Sommaire sur Inducks", "url": inducks_url}]]

    cover_url = None
    if info.get("slug"):
        cover_url = fetch_disneymagazines_cover(info.get("slug"))
        if cover_url: print(f"  [info] High quality cover found on DisneyMagazines: {cover_url}")
    if not cover_url:
        cover_url = info.get("cover_url")

    _dispatch_notification(
        info=info,
        base_caption="\n".join(lines),
        summary="",
        buttons=buttons,
        cover_url=cover_url,
        cover_filename=f"{codif}_{name}_{num}",
        message_thread_id=TELEGRAM_THREAD_ID_FR,
        publication_type="magazine",
        raw_title=f"{name} N° {num}"
    )

def _build_glenat_buttons(album: dict, raw_title: str) -> list:
    row1 = [{"text": "Voir sur Glénat", "url": album["url"]}]
    if AMAZON_AFFILIATE_TAG:
        asin = isbn13_to_isbn10(album.get("ean", ""))
        if asin: row1.append({"text": "Acheter sur Amazon", "url": f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
    return [row1, [{"text": "Sommaire sur Inducks", "url": build_glenat_inducks_url(raw_title)}]]

def notify_glenat_announce(album: dict, state: dict | None = None):
    """Glénat announcement notification (upcoming album)."""
    resolve_dbg_tome_number(album, state)
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    lines = [f"<b>Annonce — {title}</b>", ""]
    if album.get("date"): lines.append(f"🗓 Parution prévue : {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix: lines.append(f"💶 {html_lib.escape(prix)}")

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=_build_glenat_buttons(album, raw_title),
        cover_url=album.get("cover_url"),
        cover_filename=f"{album.get('ean', 'glenat')}_{raw_title}",
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
    if album.get("date"): lines.append(f"🗓 Paru le : {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix: lines.append(f"💶 {html_lib.escape(prix)}")

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=_build_glenat_buttons(album, raw_title),
        cover_url=album.get("cover_url"),
        cover_filename=f"{album.get('ean', 'glenat')}_{raw_title}",
        message_thread_id=TELEGRAM_THREAD_ID_FR,
        publication_type="glenat",
        raw_title=raw_title
    )

def notify_us_release(album: dict, state: dict | None = None):
    """US release notification (e.g., Fantagraphics)."""
    title = html_lib.escape(album.get("title", "US Disney Comic"))
    raw_title = album.get("title", "US Disney Comic")

    lines = [f"🇺🇸 <b>{title}</b>", ""]
    if album.get("date"): lines.append(f"🗓 Published on: {album['date']}")
    if album.get("price"): lines.append(f"💵 Price: {html_lib.escape(album['price'])}")

    source_name = "Marvel" if album.get("source") == "marvel" else "Fantagraphics"
    row1 = [{"text": f"View on {source_name}", "url": album["url"]}]
    if AMAZON_AFFILIATE_TAG and album.get("sku"):
        asin = isbn13_to_isbn10(album.get("sku", ""))
        if asin: row1.append({"text": "Buy on Amazon", "url": f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
    
    buttons = [row1, [{"text": "Search on Inducks", "url": f"https://inducks.org/search.php?search={quote(raw_title)}"}]]

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=buttons,
        cover_url=album.get("cover_url"),
        cover_filename=f"us_{album.get('sku', 'fanta')}_{raw_title}",
        message_thread_id=TELEGRAM_THREAD_ID_US,
        publication_type="us",
        raw_title=raw_title
    )
