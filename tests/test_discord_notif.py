"""Smoke test for the Discord webhook backend.

Dry-run by default: prints the exact payload without posting, so the shared
Inducks server never sees a half-finished test message.

    python tests/test_discord_notif.py            # preview the rendered markdown
    python tests/test_discord_notif.py --local    # full round-trip against a local
                                                  # capture server: no secret needed,
                                                  # asserts the real HTTP payload
    python tests/test_discord_notif.py --send     # post to DISCORD_WEBHOOK_URL
    python tests/test_discord_notif.py --send --admin   # also post to the staff webhook
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.abspath("."))

# The Windows console defaults to cp1252 and would choke on the emoji captions.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEND  = "--send" in sys.argv
ADMIN = "--admin" in sys.argv
LOCAL = "--local" in sys.argv

CAPTURED = []


class _Capture(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        CAPTURED.append((self.path, json.loads(body)))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass  # keep the test output readable


def start_capture_server() -> str:
    """Serves a stand-in for discord.com and returns its base webhook URL."""
    server = HTTPServer(("127.0.0.1", 0), _Capture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/api/webhooks/1/token"


if LOCAL:
    # Must land in the environment before src.config reads it at import time.
    base = start_capture_server()
    os.environ["DISCORD_WEBHOOK_URL"] = base
    os.environ["DISCORD_ADMIN_WEBHOOK_URL"] = base + "-admin"
    os.environ["DISCORD_ROLE_IDS"] = "fr:111111111111111111"
    SEND = ADMIN = True
elif os.path.exists(".env"):
    # Load local .env file (same loader as the Telegram test)
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                val = val.strip().strip('"').strip("'")
                # Same precedence as src/config.py: the real environment wins,
                # so a run can neutralise a value (e.g. DISCORD_ROLE_IDS="" to
                # test without pinging anyone) without .env clobbering it back.
                if val:
                    os.environ.setdefault(key.strip(), val)

from src.config import DISCORD_ADMIN_WEBHOOK_URL, DISCORD_ROLE_IDS, DISCORD_WEBHOOK_URL
from src.discord import build_link_line, html_to_markdown, role_mention, send_discord

# A caption in the exact HTML shape notify_magazine() produces.
CAPTION = (
    "<b>Picsou Magazine 580</b>\n\n"
    "\U0001f4b6 Price: 6,50 €\n"
    "\U0001f4c5 Published: 10/06/2026\n"
    "\U0001f4c5 On newsstands until: 15/07/2026\n\n"
    "<i>A cover summary with an &amp; ampersand and \"quotes\" to check unescaping.</i>"
)
BUTTONS = [
    [{"text": "View Source", "url": "https://direct-editeurs.fr/magazine/13159_picsou-magazine_580"}],
    [{"text": "View on Inducks", "url": "https://inducks.org/issue.php?c=fr%2FPM+580"}],
]
COVER = "https://fleuruspresse-disney.twic.pics/media/image/bf/8b/92b046384bdbd5d0a96b5640db98.jpg"

DBI_CAPTION = (
    'New DBI generated for <a href="https://direct-editeurs.fr">'
    "<b>Picsou Magazine 580</b></a>:\n"
    "<pre>issue fr/PM 580\nissuecode fr/PM 580\nprice 6,50 EUR</pre>"
)
DBI_BUTTONS = [[{"text": "Upload Scan", "url": "https://inducks.org/sendscan.php?c=fr&s=PM&i=PM+580&u=PM+580a"}]]


def preview(label: str, description: str, content: str, image_url: str | None, hook: str):
    print(f"\n=== {label} ===")
    print(f"  webhook configured: {'yes' if hook else 'NO — nothing would be sent'}")
    print(f"  content (role ping): {content!r}")
    print(f"  image: {image_url}")
    print("  description:")
    print("  " + "\n  ".join(description.splitlines()))


def build(caption: str, buttons: list) -> str:
    description = html_to_markdown(caption)
    links = build_link_line(buttons)
    return description + (f"\n\n{links}" if links else "")


def preflight() -> bool:
    """Checks each webhook actually targets its expected channel.

    GET on a webhook URL returns the webhook object, channel_id included. The
    two webhooks are trivially easy to swap, and swapping them would dump the
    DBI skeletons into the public announcements channel, so this refuses to
    send rather than let that happen.
    """
    import requests

    expected = [
        ("announcements", DISCORD_WEBHOOK_URL, os.environ.get("DISCORD_CHANNEL_ID", "")),
        ("index/staff", DISCORD_ADMIN_WEBHOOK_URL, os.environ.get("DISCORD_ADMIN_CHANNEL_ID", "")),
    ]
    ok = True
    for label, hook, want in expected:
        if not hook:
            print(f"  [skip] {label}: no webhook configured")
            continue
        try:
            info = requests.get(hook, timeout=10).json()
        except Exception as e:
            print(f"  [FAIL] {label}: unreachable ({e})")
            ok = False
            continue
        got = info.get("channel_id", "?")
        if want and got != want:
            print(f"  [FAIL] {label}: webhook posts to {got}, expected {want}")
            ok = False
        else:
            print(f"  [ok]   {label}: #{info.get('name', '?')} -> channel {got}")
    return ok


print("Role ids loaded:", json.dumps(DISCORD_ROLE_IDS, indent=2) if DISCORD_ROLE_IDS else "(none)")

if SEND and not LOCAL:
    print("Preflight:")
    if not preflight():
        sys.exit("Aborted: webhook/channel mismatch.")

# 1. Public announcement
description = build(CAPTION, BUTTONS)
content = role_mention("fr")
preview("Public announcement (fr)", description, content, COVER, DISCORD_WEBHOOK_URL)

if SEND:
    ok = send_discord(description=description, image_url=COVER, content=content)
    print(f"  -> sent: {ok}")

# 2. Staff DBI skeleton
dbi_description = build(DBI_CAPTION, DBI_BUTTONS)
preview("Staff DBI skeleton", dbi_description, "", COVER, DISCORD_ADMIN_WEBHOOK_URL)

if SEND and ADMIN:
    if not DISCORD_ADMIN_WEBHOOK_URL:
        print("  -> skipped: DISCORD_ADMIN_WEBHOOK_URL is empty")
    else:
        ok = send_discord(
            description=dbi_description,
            image_url=COVER,
            webhook_url=DISCORD_ADMIN_WEBHOOK_URL,
        )
        print(f"  -> sent: {ok}")

if LOCAL:
    print("\n=== Captured payloads ===")
    assert len(CAPTURED) == 2, f"expected 2 posts, captured {len(CAPTURED)}"

    (public_path, public), (admin_path, admin) = CAPTURED

    # The role ping must sit in `content`: Discord never highlights a mention
    # placed inside an embed.
    assert public["content"] == "<@&111111111111111111>", public["content"]
    assert public["allowed_mentions"] == {"parse": ["roles"]}, "never allow @everyone"
    assert admin["content"] == "", "the staff channel gets no ping"
    assert admin_path.endswith("-admin"), admin_path

    embed = public["embeds"][0]
    assert embed["image"]["url"] == COVER
    assert embed["color"] == 0xE4002B
    assert "**Picsou Magazine 580**" in embed["description"]
    assert "[View Source](" in embed["description"]
    assert "<b>" not in embed["description"], "HTML leaked into the Discord payload"
    assert "&amp;" not in embed["description"], "entities must be unescaped"
    assert "```" in admin["embeds"][0]["description"], "DBI must stay in a code block"
    assert len(embed["description"]) <= 4096
    assert len(public["content"]) <= 2000

    print(json.dumps(public, indent=2, ensure_ascii=False)[:600])
    print("\nAll assertions passed - payload is what Discord expects.")
elif not SEND:
    print("\nDry run. Add --local for a full round-trip, or --send to post for real.")
