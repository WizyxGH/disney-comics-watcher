import os
import sys

# Ensure check_magazines can be imported
sys.path.insert(0, os.path.abspath("."))

# Mock environment if not set, but notify_magazine needs correct Telegram credentials
# so we load them if present or ask the user to provide them
telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
telegram_chat = os.environ.get("TELEGRAM_CHAT_ID_FR") or os.environ.get("TELEGRAM_CHAT_ID")

if not telegram_token or not telegram_chat:
    print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in your environment.")
    print("You can run it like this in PowerShell:")
    print('  $env:TELEGRAM_BOT_TOKEN="your_token"; $env:TELEGRAM_CHAT_ID="your_chat_id"; python test_telegram_notif.py')
    sys.exit(1)

from check_magazines import notify_magazine

# Test data for Direct Editeurs magazine
test_magazine = {
    "codif": "14067",  # Journal de Mickey
    "numero": "3858",
    "date_mise_en_vente": "27/05/2026",
    "prix": "5,90 €",
    "cover_url": "https://cdn.direct-editeurs.fr/parutions/72/72edf1da4557889bcd92792a7bdabe78.jpg",
    "url": "https://direct-editeurs.fr/magazine/14067_le-journal-de-mickey_3858",
    "slug": "le-journal-de-mickey",
    "site_name": "LE JOURNAL DE MICKEY"
}

print(f"Sending test notification for magazine: {test_magazine['site_name']} N° {test_magazine['numero']}...")
try:
    notify_magazine(test_magazine, releve_date="15/07/2026")
    print("Test notification sent successfully! Check your Telegram channel.")
except Exception as e:
    print(f"Error sending notification: {e}")
