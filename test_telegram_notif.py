import os
import sys

# Ensure check_magazines can be imported
sys.path.insert(0, os.path.abspath("."))

telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
telegram_chat = os.environ.get("TELEGRAM_CHAT_ID_FR") or os.environ.get("TELEGRAM_CHAT_ID")

if not telegram_token or not telegram_chat:
    print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in your environment.")
    print("You can run it like this in PowerShell:")
    print('  $env:TELEGRAM_BOT_TOKEN="your_token"; $env:TELEGRAM_CHAT_ID="your_chat_id"; $env:AMAZON_AFFILIATE_TAG="your_tag"; python test_telegram_notif.py')
    sys.exit(1)

from check_magazines import notify_magazine, notify_glenat_release, fetch_glenat_details

# 1. Test Journal de Mickey (double issue)
jm_double = {
    "codif": "14067",
    "numero": "3858-3859",
    "date_mise_en_vente": "27/05/2026",
    "prix": "5,90 €",
    "cover_url": "https://fleuruspresse-disney.twic.pics/media/image/3b/16/da33e210938dbe092400db628bf7.jpg",
    "url": "https://direct-editeurs.fr/magazine/14067_le-journal-de-mickey_3858-3859",
    "slug": "le-journal-de-mickey",
    "site_name": "LE JOURNAL DE MICKEY"
}

# 2. Test Picsou Magazine
picsou_mag = {
    "codif": "13159",
    "numero": "580",
    "date_mise_en_vente": "10/06/2026",
    "prix": "6,50 €",
    "cover_url": "https://fleuruspresse-disney.twic.pics/media/image/bf/8b/92b046384bdbd5d0a96b5640db98.jpg",
    "url": "https://direct-editeurs.fr/magazine/13159_picsou-magazine_580",
    "slug": "picsou-magazine",
    "site_name": "PICSOU MAGAZINE"
}

# 3. Test Super Picsou Géant
super_picsou = {
    "codif": "14016",
    "numero": "245",
    "date_mise_en_vente": "15/06/2026",
    "prix": "7,50 €",
    "cover_url": "https://fleuruspresse-disney.twic.pics/media/image/bb/5e/a2e7ebc1340053904d08f3dc1de5.jpg",
    "url": "https://direct-editeurs.fr/magazine/14016_super-picsou-geant_245",
    "slug": "super-picsou-geant",
    "site_name": "SUPER PICSOU GEANT"
}

# 4. Test Les Chroniques de Fantomiald
fantomiald = {
    "codif": "15190",
    "numero": "35",
    "date_mise_en_vente": "20/06/2026",
    "prix": "6,90 €",
    "cover_url": "https://fleuruspresse-disney.twic.pics/media/image/4f/19/3082ea44dd61b8453d2478ed6058.jpg",
    "url": "https://direct-editeurs.fr/magazine/15190_les-chroniques-de-fantomiald_35",
    "slug": "les-chroniques-de-fantomiald",
    "site_name": "LES CHRONIQUES DE FANTOMIALD"
}

# 5. Test Glénat Album - Picsou et les bit-coincoins (Standard)
test_album = {
    "ean": "9782344062081",
    "title": "Picsou et les bit-coincoins - Collector",
    "date": "08/10/2025",
    "url": "https://www.glenat.com/glenat-disney/disney-glenat-picsou-et-les-bit-coincoins-collector-9782344062081",
    "cover_url": "https://www.images.hachette-livre.fr/media/imgArticle/GLENAT/2025/9782344062081-001-X.jpeg"
}

# 6. Test Glénat Album - Les Âges d'or de Picsou (Tome 03)
test_album_aod = {
    "ean": "9782344075210",
    "title": "Les Âges d'or de Picsou - Tome 03",
    "date": "10/06/2026",
    "url": "https://www.glenat.com/glenat-disney/les-ages-dor-de-picsou-tome-03-9782344075210/",
    "cover_url": "https://www.images.hachette-livre.fr/media/imgArticle/GLENAT/2026/9782344075210-001-X.jpeg"
}

# 7. Test Glénat Album - La Grande Histoire de Picsou (Tome 01)
test_album_ghp = {
    "ean": "9782344072578",
    "title": "La Grande Histoire de Picsou - Tome 01",
    "date": "03/12/2025",
    "url": "https://www.glenat.com/glenat-disney/la-grande-histoire-de-picsou-par-don-rosa-tome-01-9782344072578/",
    "cover_url": "https://www.images.hachette-livre.fr/media/imgArticle/GLENAT/2025/9782344072578-001-X.jpeg"
}

# Run Magazine tests
magazines = [
    ("Journal de Mickey (Double Issue)", jm_double),
    ("Picsou Magazine", picsou_mag),
    ("Super Picsou Géant", super_picsou),
    ("Les Chroniques de Fantomiald", fantomiald),
]

for name, data in magazines:
    print(f"\nSending test notification for: {name} N° {data['numero']}...")
    try:
        notify_magazine(data, releve_date="15/07/2026")
        print(f"Success for {name}!")
    except Exception as e:
        print(f"Error for {name}: {e}")

# Run Glénat Album tests
glenat_albums = [
    ("Standard Glénat Album", test_album),
    ("Les Âges d'or de Picsou", test_album_aod),
    ("La Grande Histoire de Picsou", test_album_ghp),
]

for name, album in glenat_albums:
    print(f"\nSending test notification for Glénat album: {album['title']}...")
    try:
        details = fetch_glenat_details(album["url"])
        album["price"] = details.get("price") or album.get("price")
        album["summary"] = details.get("summary") or album.get("summary")
        album["cover_url"] = details.get("cover_url") or album.get("cover_url")
        notify_glenat_release(album)
        print(f"Success for {name}!")
    except Exception as e:
        print(f"Error for {name}: {e}")
