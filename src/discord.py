"""Discord webhook transport for watcher notifications.

Messages are plain text, not embeds: the caption goes in the message body,
the cover is uploaded as an attachment, and link previews are suppressed so
the Source/Inducks links don't each spawn a preview card.
"""

import json
import re
import html as html_lib
import time
import requests

from src.config import DISCORD_WEBHOOK_URL, DISCORD_ROLE_IDS
from src.utils import get_session

CONTENT_MAX = 2000             # Discord hard limit per message
IMAGE_MAX = 8 * 1024 * 1024    # stay under the webhook upload limit
SUPPRESS_EMBEDS = 1 << 2       # message flag: no link previews
FENCE = "```"

_IMAGE_EXT = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}

# Compiled once: html_to_markdown runs on every notification of every run.
_RE_PRE  = re.compile(r'<pre>(.*?)</pre>', re.S)
_RE_LINK = re.compile(r'<a href="([^"]+)">(.*?)</a>', re.S)
_RE_BOLD = re.compile(r'</?b>')
_RE_ITAL = re.compile(r'</?i>')
_RE_TAG  = re.compile(r'<[^>]+>')

# One pooled connection to discord.com instead of a fresh TLS handshake per message.
_session = requests.Session()


def html_to_markdown(text: str) -> str:
    """Converts the Telegram HTML captions to Discord markdown.

    Only the subset the watcher emits is handled: <b>, <i>, <a>, <pre>.
    Keeping one caption format for both backends avoids duplicating every
    message builder.
    """
    if not text:
        return ""
    out = _RE_PRE.sub(lambda m: f"{FENCE}\n{m.group(1)}\n{FENCE}", text)
    out = _RE_LINK.sub(r'[\2](\1)', out)
    out = _RE_BOLD.sub('**', out)
    out = _RE_ITAL.sub('*', out)
    out = _RE_TAG.sub('', out)
    return html_lib.unescape(out)


def role_mention(country: str) -> str:
    """Returns the '<@&id>' mention for a country role, or '' if none configured."""
    role_id = DISCORD_ROLE_IDS.get((country or "").lower())
    return f"<@&{role_id}>" if role_id else ""


def build_link_line(buttons: list | None) -> str:
    """Renders button rows as a markdown link line.

    Webhooks cannot send interactive components, so buttons become inline links.
    """
    if not buttons:
        return ""
    links = [
        f"[{btn['text']}]({btn['url']})"
        for row in buttons
        for btn in row
        if btn.get("url") and btn.get("text")
    ]
    return " • ".join(links)


def split_message(text: str, limit: int = CONTENT_MAX) -> list[str]:
    """Splits text into messages of at most `limit` characters, on line breaks.

    A code block cut in two is closed at the end of one part and reopened at
    the start of the next, so a long DBI skeleton stays copyable.
    """
    closing = len("\n" + FENCE)
    width = limit - closing - len(FENCE + "\n")  # room for a line in a reopened block
    parts, current, in_code = [], "", False

    for raw in text.split("\n"):
        # A line longer than a message is hard-cut; captions never have one,
        # but it must neither loop nor overflow.
        for line in [raw[i:i + width] for i in range(0, len(raw), width)] or [""]:
            opens_or_closes = line.strip().startswith(FENCE)
            in_code_after = in_code != opens_or_closes
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) + (closing if in_code_after else 0) <= limit:
                current, in_code = candidate, in_code_after
                continue
            parts.append(current + ("\n" + FENCE if in_code else ""))
            current = (FENCE + "\n" if in_code else "") + line
            in_code = in_code_after

    if current or not parts:
        parts.append(current)
    return parts


def _fetch_image(url: str) -> tuple[str, bytes, str] | None:
    """Downloads a cover for upload, or returns None to send the text alone."""
    try:
        r = get_session().get(url, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  [warn] Discord: cover not attached ({e})")
        return None
    mime = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    if not mime.startswith("image/") or len(r.content) > IMAGE_MAX:
        print(f"  [warn] Discord: cover not attached ({mime}, {len(r.content)} bytes)")
        return None
    return f"cover{_IMAGE_EXT.get(mime, '.jpg')}", r.content, mime


def _post(hook: str, payload: dict, image: tuple[str, bytes, str] | None, retries: int) -> bool:
    """Posts one message, retrying on errors and honouring 429 retry_after."""
    delay = 2
    for attempt in range(retries):
        try:
            if image:
                resp = _session.post(
                    hook,
                    data={"payload_json": json.dumps(payload)},
                    files={"files[0]": image},
                    timeout=30,
                )
            else:
                resp = _session.post(hook, json=payload, timeout=15)

            if resp.status_code == 429:
                retry_after = resp.json().get("retry_after", delay)
                print(f"  [429] Discord rate limit — waiting {retry_after}s…")
                time.sleep(float(retry_after))
                continue

            resp.raise_for_status()
            return True

        except requests.RequestException as e:
            print(f"  [error] Discord (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)
    return False


def send_discord(
    text: str,
    image_url: str | None = None,
    mention: str = "",
    webhook_url: str = "",
    retries: int = 5,
) -> bool:
    """Posts a plain-text message (plus the cover as an attachment) to a webhook.

    mention: role ping put on the first line; only role pings are ever allowed.
    Text beyond Discord's 2000-character limit is split over several messages,
    the cover going with the last one. Returns True if every part was sent.
    """
    hook = webhook_url or DISCORD_WEBHOOK_URL
    if not hook:
        print("  [warn] No Discord webhook configured.")
        return False

    body = f"{mention}\n{text}" if mention else text
    parts = split_message(body.strip())
    image = _fetch_image(image_url) if image_url else None

    for i, part in enumerate(parts):
        payload = {
            "content": part,
            # Never @everyone, never mass user pings.
            "allowed_mentions": {"parse": ["roles"]},
            "flags": SUPPRESS_EMBEDS,
        }
        if not _post(hook, payload, image if i == len(parts) - 1 else None, retries):
            print("  [FAILURE] Discord notification not sent.")
            return False
    return True
