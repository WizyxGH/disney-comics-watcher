"""Telegram transport, cover image download, and admin alert helpers."""
import os
import time
import requests

from src.config import (
    TELEGRAM_API, TELEGRAM_CHAT_ID,
    DISCORD_ADMIN_WEBHOOK_URL, NOTIFY_BACKENDS,
)
from src.discord import send_discord, build_link_line, html_to_markdown
from src.utils import fetch_image_bytes

# One pooled connection to api.telegram.org, mirroring the one in src/discord.py.
_tg_session = requests.Session()


def download_cover(url: str | None, filename: str):
    """Downloads and saves the cover image to the 'covers' directory."""
    if not url:
        return
    os.makedirs("covers", exist_ok=True)

    filename = "".join(c for c in filename if c.isalnum() or c in (" ", ".", "_", "-")).strip()
    filename = filename.replace(" ", "_")
    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
        filename += ".jpg"

    filepath = os.path.join("covers", filename)
    if os.path.exists(filepath):
        return

    try:
        fetched = fetch_image_bytes(url, timeout=15)
        if not fetched:
            raise RuntimeError("empty or non-image response")
        with open(filepath, "wb") as f:
            f.write(fetched[0])
        print(f"  [info] Cover saved: {filepath}")
    except Exception as e:
        print(f"  [warn] Failed to download cover {url}: {e}")


def send_telegram(
    photo_url: str | None,
    caption: str,
    buttons: list | None = None,
    retries: int = 5,
    chat_id: str = TELEGRAM_CHAT_ID,
    message_thread_id: str | None = None,
):
    """Sends a Telegram message with a photo (sendPhoto) or text only (sendMessage).
    Automatically handles rate limits (429) and inaccessible photos.
    Returns the Telegram message_id (int) if successful, None otherwise."""
    delay = 2
    reply_markup = {"inline_keyboard": buttons} if buttons else None

    if photo_url and len(caption) > 1024:
        photo_url = None

    for attempt in range(retries):
        try:
            if photo_url:
                payload = {
                    "chat_id": chat_id,
                    "photo": photo_url,
                    "caption": caption[:1024],
                    "parse_mode": "HTML",
                }
                if message_thread_id:
                    payload["message_thread_id"] = int(message_thread_id)
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = _tg_session.post(f"{TELEGRAM_API}/sendPhoto", json=payload, timeout=15)
                if resp.status_code == 400:
                    print(f"  [debug] Telegram 400 error: {resp.text}")
                    desc = resp.json().get("description", "").lower()
                    if any(k in desc for k in ("photo", "wrong url", "failed to get", "url", "web page content", "caption is too long", "caption too long")):
                        print(f"  [warn] Photo/caption issue ({desc}) -> fallback to text")
                        photo_url = None
                        continue
            else:
                payload = {
                    "chat_id": chat_id,
                    "text": caption[:4096],
                    "parse_mode": "HTML",
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


def send_admin(text_html: str, photo_url: str | None = None, buttons: list | None = None):
    """Sends a message to the admin DM (Telegram) and admin channel (Discord):
    DBI skeletons, and the watcher's own alerts about sources gone silent."""
    admin_id = os.environ.get("TELEGRAM_ADMIN_ID")
    if "telegram" in NOTIFY_BACKENDS and admin_id:
        send_telegram(
            photo_url=photo_url if len(text_html) <= 1024 else None,
            caption=text_html,
            chat_id=admin_id,
            buttons=buttons,
        )

    if "discord" in NOTIFY_BACKENDS and DISCORD_ADMIN_WEBHOOK_URL:
        description = html_to_markdown(text_html)
        links = build_link_line(buttons)
        if links:
            description += f"\n\n{links}"
        send_discord(text=description, image_url=photo_url, webhook_url=DISCORD_ADMIN_WEBHOOK_URL)
