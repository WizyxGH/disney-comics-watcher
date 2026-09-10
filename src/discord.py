"""Discord webhook transport for watcher notifications."""

import re
import html as html_lib
import time
import requests

from src.config import DISCORD_WEBHOOK_URL, DISCORD_ROLE_IDS

# Discord hard limits
CONTENT_MAX     = 2000
EMBED_DESC_MAX  = 4096
EMBED_TITLE_MAX = 256

EMBED_COLOR = 0xE4002B  # Disney red

# Compiled once: html_to_markdown runs on every notification of every run.
_RE_PRE  = re.compile(r'<pre>(.*?)</pre>', re.S)
_RE_LINK = re.compile(r'<a href="([^"]+)">(.*?)</a>', re.S)
_RE_BOLD = re.compile(r'</?b>')
_RE_ITAL = re.compile(r'</?i>')
_RE_TAG  = re.compile(r'<[^>]+>')

# One pooled connection to discord.com instead of a fresh TLS handshake per embed.
_session = requests.Session()


def html_to_markdown(text: str) -> str:
    """Converts the Telegram HTML captions to Discord markdown.

    Only the subset the watcher emits is handled: <b>, <i>, <a>, <pre>.
    Keeping one caption format for both backends avoids duplicating every
    message builder.
    """
    if not text:
        return ""
    out = re.sub(r'<pre>(.*?)</pre>', r'```\n\1\n```', text, flags=re.S)
    out = re.sub(r'<a href="([^"]+)">(.*?)</a>', r'[\2](\1)', out, flags=re.S)
    out = re.sub(r'</?b>', '**', out)
    out = re.sub(r'</?i>', '*', out)
    out = re.sub(r'<[^>]+>', '', out)
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


def send_discord(
    description: str,
    title: str | None = None,
    url: str | None = None,
    image_url: str | None = None,
    content: str = "",
    webhook_url: str = "",
    retries: int = 5,
) -> bool:
    """Posts an embed to a Discord webhook.

    content: plain text above the embed — this is where role mentions go
             (mentions inside embeds are never highlighted by Discord).
    Handles rate limits (429) with the server-provided retry_after.
    Returns True on success.
    """
    hook = webhook_url or DISCORD_WEBHOOK_URL
    if not hook:
        print("  [warn] No Discord webhook configured.")
        return False

    embed = {
        "description": description[:EMBED_DESC_MAX],
        "color": EMBED_COLOR,
    }
    if title:
        embed["title"] = title[:EMBED_TITLE_MAX]
    if url:
        embed["url"] = url
    if image_url:
        embed["image"] = {"url": image_url}

    payload = {
        "content": content[:CONTENT_MAX],
        "embeds": [embed],
        # Only role pings are allowed: never @everyone, never mass user pings.
        "allowed_mentions": {"parse": ["roles"]},
    }

    delay = 2
    for attempt in range(retries):
        try:
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

    print("  [FAILURE] Discord notification not sent.")
    return False
