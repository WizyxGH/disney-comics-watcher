import os
import sys

# Ensure check_magazines can be imported
sys.path.insert(0, os.path.abspath("."))

# Load local .env file if it exists
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
telegram_chat = os.environ.get("TELEGRAM_CHAT_ID_FR") or os.environ.get("TELEGRAM_CHAT_ID")

if not telegram_token or not telegram_chat:
    print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in your environment.")
    print("You can run it like this in PowerShell:")
    print('  $env:TELEGRAM_BOT_TOKEN="your_token"; $env:TELEGRAM_CHAT_ID="your_chat_id"; $env:AMAZON_AFFILIATE_TAG="your_tag"; python test_telegram_notif.py')
    # sys.exit(1)

from src.notifications import notify_international_comic, notify_magazine, notify_glenat_release
from src.scrapers.fr import fetch_glenat_details

print('\nSending test notification for US Comic...')
us_comic = {'id': '123456', 'title': 'Uncle Scrooge #1', 'date': '15/07/2026', 'price': '.99', 'url': 'https://marvel.com', 'cover_url': 'https://i.annihil.us/u/prod/marvel/i/mg/3/40/4bc63b9278bd1/detail.jpg'}
notify_international_comic(us_comic, country="us", event_type="release")

print('\nSending test notification for DE Comic...')
de_comic = {'id': 'MM26-15', 'title': 'Micky Maus Magazin Nr. 15', 'date': '20/07/2026', 'price': '4,50 ', 'url': 'https://egmont.de', 'cover_url': 'https://www.egmont-shop.de/globalassets/egmont/produkte/micky-maus-magazin-15-2024.png'}
notify_international_comic(de_comic, country="de", event_type="release")

print('\nSending test notification for DE LTB Comic...')
de_ltb = {'id': 'LTB-613', 'title': 'Lustiges Taschenbuch Nr. 613', 'date': '20/07/2026', 'price': '7,99 ', 'url': 'https://lustiges-taschenbuch.de', 'cover_url': 'https://www.lustiges-taschenbuch.de/sites/default/files/styles/ltb_cover_medium/public/cover/ltb-613.jpg'}
notify_international_comic(de_ltb, country="de", event_type="release")

print('\nSending test notification for GR Comic...')
gr_comic = {'id': 'MM629', 'title': 'Μίκυ Μάους #629', 'date': '15/07/2026', 'price': '1,90 ', 'url': 'https://kathimerini.gr', 'cover_url': 'https://i.prcdn.co/img?cid=464B&page=1&height=1000'}
notify_international_comic(gr_comic, country="gr", event_type="release")

# 1. Test Journal de Mickey (double issue)
jm_double = {
    "codif": "14067",
    "numero": "3858-3859",
    "date_mise_en_vente": "27/05/2026",
    "prix": "5,90 €",
    "cover_url": "https://fleuruspresse-disney.twic.pics/media/image/3b/16/da33e210938dbe092400db628bf7.jpg",
    "url": "https://direct-editeurs.fr/magazine/14067_le-journal-de-mickey_3858",
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

# 5. Test SPG HS Les Méchants
spg_hs_mechants = {
    "codif": "11065",
    "numero": "1",
    "date_mise_en_vente": "06/06/2026",
    "prix": "6,99 €",
    "cover_url": "https://catalogueproduits.mlp.fr/Images/Grande_couvertures/5357208.jpg",
    "url": "https://catalogueproduits.mlp.fr/produit.aspx?tit_code=1VNav4SoK%2Bk%3D&par_num=Y8rsBoIKnD8%3D",
    "slug": "11065",
    "site_name": "Les grands méchants",
    "releve_date": "04/09/2026"
}

# 6. Test Glénat Album - Picsou et les bit-coincoins (Standard)
test_album = {
    "ean": "9782344062081",
    "title": "Picsou et les bit-coincoins - Collector",
    "date": "08/10/2025",
    "url": "https://www.glenat.com/glenat-disney/disney-glenat-picsou-et-les-bit-coincoins-collector-9782344062081",
    "cover_url": "https://www.images.hachette-livre.fr/media/imgArticle/GLENAT/2025/9782344062081-001-X.jpeg",
    "collection_label": "Créations originales"
}

# 7. Test Glénat Album - Les Âges d'or de Picsou (Tome 03)
test_album_aod = {
    "ean": "9782344075210",
    "title": "Les Âges d'or de Picsou - Tome 03",
    "date": "10/06/2026",
    "url": "https://www.glenat.com/glenat-disney/les-ages-dor-de-picsou-tome-03-9782344075210/",
    "cover_url": "https://www.images.hachette-livre.fr/media/imgArticle/GLENAT/2026/9782344075210-001-X.jpeg"
}

# 8. Test Glénat Album - La Grande Histoire de Picsou (Tome 01)
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
    ("SPG HS Les Méchants", spg_hs_mechants),
]

for name, data in magazines:
    print(f"\nSending test notification for: {name} N° {data['numero']}...")
    try:
        releve = data.get("releve_date") or "15/07/2026"
        notify_magazine(data, releve_date=releve)
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
        for k, v in details.items():
            if v is not None:
                album[k] = v
        notify_glenat_release(album)
        print(f"Success for {name}!")
    except Exception as e:
        print(f"Error for {name}: {e}")
