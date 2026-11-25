"""Notification formatting and orchestration across Telegram, Discord, and DBI generation."""
import os
import re
import html as html_lib
import time
from urllib.parse import quote_plus

from src.config import (
    TELEGRAM_CHAT_ID, TELEGRAM_THREADS,
    NOTIFY_BACKENDS, OVERRIDES, SITE_BASE, SUPPORTED_COUNTRIES,
)
from src import db as _db
from src.discord import send_discord, role_mention, build_link_line, html_to_markdown
from src.telegram import download_cover, send_telegram, send_admin
from src.inducks_links import (
    INDUCKS_BUTTONS, inducks_button, build_cvsedit_url, _get_inputfilename_for_issue,
)
from src.utils import (
    format_price_fr, get_session, truncate_summary,
    is_fully_indexed_in_inducks, cover_filename,
)
from src.dbi.generator import generate_dbi_skeleton
from src.dbi.mappers import resolve_magazine_metadata, resolve_glenat_metadata, resolve_comic_metadata
from src.gemini_analyzer import analyze_cover_with_gemini


def resolve_dbg_tome_number(album: dict, state: dict | None = None):
    """Resolves and extrapolates the next issue number for Disney By Glénat (DBG) albums."""
    title = album.get("title", "")
    if re.search(r"tome\s+\d+", title, re.I) or "glenat" not in album.get("url", ""):
        return
    # Placeholder if DBG extrapolation is needed in future


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
            timeout=10,
        )
        if r.status_code == 200:
            m = re.search(r'"(https://fleuruspresse-disney\.twic\.pics/media/[^"]+\.jpg)[^"]*"', r.text)
            if m:
                return m.group(1)
            m = re.search(r'"(https://www\.disneymagazines\.fr/media/cache/[^"]+\.jpg)"', r.text)
            if m:
                return m.group(1)
            m = re.search(r'src="(/media/image/[^"]+\.jpg)"', r.text)
            if m:
                return f"https://www.disneymagazines.fr{m.group(1)}"
    except Exception as e:
        print(f"  [warn] Unable to retrieve cover from DisneyMagazines for {slug}: {e}")
    return None


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
        "placeholder/default/", "placeholder_1.jpg", "placeholder.jpg",
        "coming-soon", "coming_soon", "comingsoon", "no-image", "no_image",
        "coverabbildung-nicht-verfugbar",
    ))


def _dispatch_notification(
    info: dict,
    base_caption: str,
    summary: str,
    buttons: list,
    cover_url: str | None,
    publication_type: str,
    raw_title: str,
):
    """Common pipeline: deduplicates cover, computes lengths, sends Telegram & Discord, analyzes cover, sends DBI."""
    if _is_placeholder_cover(cover_url):
        cover_url = None

    if "fr" in (publication_type or "").lower() or publication_type == "magazine":
        country = "fr"
    elif publication_type in ("glenat",):
        country = "fr"
    else:
        country = publication_type

    caption = base_caption
    if summary:
        max_len = 1024 if cover_url else 4096
        avail = max_len - len(base_caption) - 10
        if avail > 30:
            trunc_sum = truncate_summary(summary, max_len=avail)
            caption = f"{base_caption}\n\n{html_lib.escape(trunc_sum)}"

    issue_path = get_issue_path_from_info(info, publication_type)
    cover_name = cover_filename(issue_path, country)
    is_fully_indexed = is_fully_indexed_in_inducks(issue_path)

    if is_fully_indexed:
        print(f"  [info] Issue {issue_path} is completely indexed on Inducks. Skipping cover download and DBI generation.")

    if cover_url and not is_fully_indexed:
        download_cover(cover_url, cover_name)

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

    if "telegram" in NOTIFY_BACKENDS:
        if TELEGRAM_CHAT_ID:
            send_telegram(
                cover_url,
                caption,
                buttons=final_buttons,
                message_thread_id=TELEGRAM_THREADS.get(country),
            )
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
            char_list = ", ".join(f"{c['name_fr']} ({c['code']})" if c.get("code") else c["name_fr"] for c in characters)
            print(f"  [Gemini] Detected characters: {char_list}")
            info["characters"] = characters

    if not is_fully_indexed:
        dbi_content = generate_dbi_skeleton(info, publication_type=publication_type, overrides=OVERRIDES)

        if dbi_content:
            dbi_lines = [line for line in dbi_content.strip().split("\n") if not line.startswith("^^ Source")]
            clean_dbi = html_lib.escape("\n".join(dbi_lines).strip())

            source_url = info.get("url")
            title_html = f'<a href="{html_lib.escape(source_url)}"><b>{html_lib.escape(raw_title)}</b></a>' if source_url else f'<b>{html_lib.escape(raw_title)}</b>'
            dm_text = f"New DBI generated for {title_html}:\n<pre>{clean_dbi}</pre>"

            dm_buttons = None
            if issue_path and "UNK" not in issue_path:
                country_part = issue_path.split("/", 1)[0]
                issue_part = issue_path.split("/", 1)[1] if "/" in issue_path else issue_path
                s_part = quote_plus(issue_part.split(" ")[0] if " " in issue_part else issue_part)
                i_part = quote_plus(issue_part)
                u_part = f"{i_part}a"
                upload_url = f"https://inducks.org/sendscan.php?c={quote_plus(country_part)}&s={s_part}&i={i_part}&u={u_part}"
                edit_url = build_cvsedit_url(issue_path)

                dm_buttons = [
                    [
                        {"text": "Upload Scan", "url": upload_url},
                        {"text": "Edit using SVN", "url": edit_url},
                    ]
                ]

            send_admin(dm_text, photo_url=cover_url, buttons=dm_buttons)


def notify_magazine(info: dict, releve_date: str | None = None):
    """Sends the Telegram notification for a new magazine issue."""
    codif = info["codif"]
    ov = OVERRIDES.get(codif, {})
    name = ov.get("name") or info.get("site_name") or info.get("slug") or codif
    num = info.get("numero", "?")
    prix = format_price_fr(info.get("prix"))
    date = info.get("date_mise_en_vente")
    url = info.get("url", SITE_BASE)

    title_line = f"<b>{html_lib.escape(name)} {num}</b>"
    lines = [title_line, ""]
    if date:
        lines.append(f"Released: {html_lib.escape(date)}")
    if releve_date:
        lines.append(f"On newsstands until: {html_lib.escape(releve_date)}")
    if prix:
        lines.append(f"Price: {html_lib.escape(prix)}")

    buttons = [
        [{"text": "View Source", "url": url}],
        [{"text": "Search on Inducks", "url": ""}],
    ]

    cover_url = info.get("cover_url")
    if info.get("slug") and not cover_url:
        cover_url = fetch_disneymagazines_cover(info["slug"])

    _dispatch_notification(
        info=info,
        base_caption="\n".join(lines),
        summary="",
        buttons=buttons,
        cover_url=cover_url,
        publication_type="magazine",
        raw_title=f"{name} {num}",
    )


def _build_glenat_buttons(album: dict, raw_title: str) -> list:
    row1 = [{"text": "View Source", "url": album["url"]}]
    return [row1, [{"text": "Search on Inducks", "url": ""}]]


def notify_glenat_announce(album: dict, state: dict | None = None):
    """Glénat announcement notification (upcoming album)."""
    resolve_dbg_tome_number(album, state)
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    lines = [f"<b>Announcement — {title}</b>", ""]
    if album.get("date"):
        lines.append(f"Expected release: {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix:
        lines.append(f"Price: {html_lib.escape(prix)}")

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=_build_glenat_buttons(album, raw_title),
        cover_url=album.get("cover_url"),
        publication_type="glenat",
        raw_title=raw_title,
    )


def notify_glenat_release(album: dict, state: dict | None = None):
    """Glénat release notification (album available in bookstores)."""
    resolve_dbg_tome_number(album, state)
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    lines = [f"<b>{title}</b>", ""]
    if album.get("date"):
        lines.append(f"Released: {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix:
        lines.append(f"Price: {html_lib.escape(prix)}")

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=_build_glenat_buttons(album, raw_title),
        cover_url=album.get("cover_url"),
        publication_type="glenat",
        raw_title=raw_title,
    )


def notify_international_comic(album: dict, state: dict | None = None, country: str = "us", event_type: str = "announce"):
    """Generic notification function for international releases (US, DE, GR, etc.)."""
    title = html_lib.escape(album.get("title", f"{country.upper()} Disney Comic"))
    raw_title = album.get("title", f"{country.upper()} Disney Comic")

    date_prefix = "Expected release:" if event_type == "announce" else "Released:"
    lines = [f"<b>Announcement — {title}</b>" if event_type == "announce" else f"<b>{title}</b>", ""]
    if album.get("date"):
        lines.append(f"{date_prefix} {album['date']}")
    if album.get("price"):
        lines.append(f"Price: {html_lib.escape(album['price'])}")

    buttons = [[{"text": "View Source", "url": album.get("url", "")}], [{"text": "Search on Inducks", "url": ""}]]

    _dispatch_notification(
        info=album,
        base_caption="\n".join(lines),
        summary=album.get("summary", ""),
        buttons=buttons,
        cover_url=album.get("cover_url"),
        publication_type=country,
        raw_title=raw_title,
    )
