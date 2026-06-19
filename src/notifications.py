import os
import re
import html as html_lib
import time
import requests
from urllib.parse import quote, quote_plus
from src.config import TELEGRAM_API, TELEGRAM_CHAT_ID, OVERRIDES, AMAZON_AFFILIATE_TAG, SITE_BASE
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


def send_telegram(photo_url: str | None, caption: str, buttons: list | None = None, retries: int = 5):
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
                    "chat_id":    TELEGRAM_CHAT_ID,
                    "photo":      photo_url,
                    "caption":    caption,
                    "parse_mode": "HTML",
                }
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
                    "chat_id":                  TELEGRAM_CHAT_ID,
                    "text":                     caption[:4096],
                    "parse_mode":               "HTML",
                    "disable_web_page_preview": True,
                }
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
            # 1st choice: twic.pics URL (native CDN, higher quality) — remove query parameters
            m = re.search(r'"(https://fleuruspresse-disney\.twic\.pics/media/[^"]+\.jpg)[^"]*"', r.text)
            if m:
                return m.group(1)
            # 2nd choice: Google Merchant cache URL on disneymagazines.fr
            m = re.search(r'"(https://www\.disneymagazines\.fr/media/cache/[^"]+\.jpg)"', r.text)
            if m:
                return m.group(1)
            # 3rd choice: relative src
            m = re.search(r'src="(/media/image/[^"]+\.jpg)"', r.text)
            if m:
                return f"https://www.disneymagazines.fr{m.group(1)}"
    except Exception as e:
        print(f"  [warn] Unable to retrieve cover from DisneyMagazines for {slug}: {e}")
    return None


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
    if prix:
        lines.append(f"💶 {html_lib.escape(prix)}")
    if date:
        lines.append(f"📅 Paru le : {date}")
    if releve_date:
        lines.append(f"📅 En kiosque jusqu'au : {releve_date}")

    # Boutons inline keyboard
    inducks_url = build_inducks_url(ov.get("inducks"), num)
    if not inducks_url:
        inducks_url = f"https://inducks.org/search.php?search={quote(f'{name} {num}')}"
    btn_text = "Voir sur MLP" if "mlp.fr" in url.lower() else "Voir sur Direct-éditeurs"
    buttons = [
        [{"text": btn_text, "url": url}],
        [{"text": "Sommaire sur Inducks", "url": inducks_url}],
    ]

    # Try to retrieve a better quality cover from DisneyMagazines first
    cover_url = None
    if info.get("slug"):
        cover_url = fetch_disneymagazines_cover(info.get("slug"))
        if cover_url:
            print(f"  [info] High quality cover found on DisneyMagazines: {cover_url}")
    if not cover_url:
        cover_url = info.get("cover_url")

    send_telegram(cover_url, "\n".join(lines), buttons=buttons)
    time.sleep(1)  # throttle

    # Try to analyze cover with Gemini if API key is present
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and cover_url:
        print(f"  [Gemini] Analyzing cover for {name} N° {num}...")
        analysis = analyze_cover_with_gemini(cover_url, api_key)
        cover_title = analysis.get("title")
        characters = analysis.get("characters", [])
        if cover_title:
            print(f"  [Gemini] Extracted title: '{cover_title}'")
            info["cover_title"] = cover_title
        if characters:
            char_list = ", ".join(f"{c['name_fr']} ({c['code']})" if c.get('code') else c['name_fr'] for c in characters)
            print(f"  [Gemini] Detected characters: {char_list}")
            info["characters"] = characters

    # Generation of the Inducks pre-index skeleton
    generate_dbi_skeleton(info, publication_type="magazine", overrides=OVERRIDES)


def build_glenat_inducks_url(title: str) -> str:
    """Builds the Inducks URL for a Glénat album (direct page if possible, otherwise search)."""
    title_lower = title.lower()
    tome_match = re.search(r'(?:tome|t\.)\s*(\d+)', title_lower)
    tome_num = int(tome_match.group(1)) if tome_match else None

    # 1. La Grande Histoire/Épopée de Picsou (Don Rosa) -> GHP code
    if "grande histoire de picsou" in title_lower or "grande epopee de picsou" in title_lower or "grande épopée de picsou" in title_lower:
        if tome_num is not None:
            code = f"fr/GHP{str(tome_num).rjust(4)}"
            return f"https://inducks.org/issue.php?c={quote_plus(code)}"
        return "https://inducks.org/publication.php?c=fr/GHP"

    # 2. Les Âges d'or (Picsou, Donald, Mickey, etc.) -> AOD code
    if "ages d'or" in title_lower or "âges d'or" in title_lower or "age d'or" in title_lower or "âge d'or" in title_lower:
        if tome_num is not None:
            code = f"fr/AOD{str(tome_num).rjust(4)}"
            return f"https://inducks.org/issue.php?c={quote_plus(code)}"
        return "https://inducks.org/publication.php?c=fr/AOD"

    return f"https://inducks.org/search.php?search={quote(title)}"


def notify_glenat_announce(album: dict, state: dict | None = None):
    """Glénat announcement notification (upcoming album)."""
    resolve_dbg_tome_number(album, state)
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    # 1. Caption: metadata + truncated summary
    meta_lines = [f"<b>Annonce — {title}</b>", ""]
    if album.get("date"):
        meta_lines.append(f"🗓 Parution prévue : {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix:
        meta_lines.append(f"💶 {html_lib.escape(prix)}")

    base_caption = "\n".join(meta_lines)
    summary = album.get("summary", "")
    if summary:
        available = 1024 - len(base_caption) - 40
        truncated = truncate_summary(summary, max_len=max(50, available))
        caption = base_caption + f"\n\n<i>{html_lib.escape(truncated)}</i>"
    else:
        caption = base_caption

    # 2. Inline keyboard buttons
    row1 = [{"text": "Voir sur Glénat", "url": album["url"]}]
    if AMAZON_AFFILIATE_TAG:
        asin = isbn13_to_isbn10(album.get("ean", ""))
        if asin:
            row1.append({"text": "Acheter sur Amazon", "url": f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
    row2 = [{"text": "Sommaire sur Inducks", "url": build_glenat_inducks_url(raw_title)}]
    buttons = [row1, row2]

    send_telegram(album.get("cover_url"), caption, buttons=buttons)
    time.sleep(1)

    # Try to analyze cover with Gemini if API key is present
    cover_url = album.get("cover_url")
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and cover_url:
        print(f"  [Gemini] Analyzing cover for Glénat album '{raw_title}'...")
        analysis = analyze_cover_with_gemini(cover_url, api_key)
        characters = analysis.get("characters", [])
        if characters:
            char_list = ", ".join(f"{c['name_fr']} ({c['code']})" if c.get('code') else c['name_fr'] for c in characters)
            print(f"  [Gemini] Detected characters: {char_list}")
            album["characters"] = characters

    # Generation of the Inducks pre-index skeleton
    generate_dbi_skeleton(album, publication_type="glenat", overrides=OVERRIDES)


def notify_glenat_release(album: dict, state: dict | None = None):
    """Glénat release notification (album available in bookstores)."""
    resolve_dbg_tome_number(album, state)
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    # 1. Caption: metadata + truncated summary
    meta_lines = [f"<b>{title}</b>", ""]
    if album.get("date"):
        meta_lines.append(f"🗓 Paru le : {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix:
        meta_lines.append(f"💶 {html_lib.escape(prix)}")

    base_caption = "\n".join(meta_lines)
    summary = album.get("summary", "")
    if summary:
        available = 1024 - len(base_caption) - 40
        truncated = truncate_summary(summary, max_len=max(50, available))
        caption = base_caption + f"\n\n<i>{html_lib.escape(truncated)}</i>"
    else:
        caption = base_caption

    # 2. Inline keyboard buttons
    row1 = [{"text": "Voir sur Glénat", "url": album["url"]}]
    if AMAZON_AFFILIATE_TAG:
        asin = isbn13_to_isbn10(album.get("ean", ""))
        if asin:
            row1.append({"text": "Acheter sur Amazon", "url": f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
    row2 = [{"text": "Sommaire sur Inducks", "url": build_glenat_inducks_url(raw_title)}]
    buttons = [row1, row2]

    send_telegram(album.get("cover_url"), caption, buttons=buttons)
    time.sleep(1)

    # Try to analyze cover with Gemini if API key is present
    cover_url = album.get("cover_url")
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and cover_url:
        print(f"  [Gemini] Analyzing cover for Glénat album '{raw_title}'...")
        analysis = analyze_cover_with_gemini(cover_url, api_key)
        characters = analysis.get("characters", [])
        if characters:
            char_list = ", ".join(f"{c['name_fr']} ({c['code']})" if c.get('code') else c['name_fr'] for c in characters)
            print(f"  [Gemini] Detected characters: {char_list}")
            album["characters"] = characters

    # Generation of the Inducks pre-index skeleton
    generate_dbi_skeleton(album, publication_type="glenat", overrides=OVERRIDES)


