import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from src.utils import get_session

_SE_PAGES = [
    ("/serier-och-humor/kalle-anka-och-co", "se/KA", "Kalle Anka & C:o"),
    ("/serier-och-humor/kalle-ankas-pocket", "se/KAP", "Kalle Ankas Pocket"),
    ("/barn-och-ungdom/kalle-anka-extra", "se/KAE", "Kalle Anka Klassiker"),
    ("/barn-och-ungdom/kalle-anka-junior", "se/KAJ", "Kalle Anka Junior"),
    ("/barn-och-ungdom/kalle-ankas-pocket-special", "se/KAPS", "Kalle Ankas Pocket Special"),
    ("/serier-och-humor/kalle-anka-julalbum", "se/KAJA", "Kalle Anka Julalbum"),
    ("/barn-och-ungdom/kalle-anka-onskar-god-jul", "se/KAGJ", "Kalle Anka Önskar God Jul"),
]

def discover_se() -> list[dict]:
    """
    Discovers Swedish Disney comic magazines from Tidningskungen (Story House Egmont Sweden).
    Covers Kalle Anka & C:o, Kalle Ankas Pocket, Kalle Anka Klassiker, etc.
    """
    s = get_session()
    result = []
    seen = set()
    base_url = "https://www.tidningskungen.se"

    for path, pub_code, default_title in _SE_PAGES:
        url = urljoin(base_url, path)
        try:
            r = s.get(url, timeout=15)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, 'html.parser')
            h1 = soup.find('h1')
            page_title = h1.get_text(strip=True) if h1 else default_title

            # Find cover image
            img = (
                soup.find('img', src=re.compile(r'tidningskungen\.se/upl/'))
                or soup.find('img', class_=re.compile(r'cover|product|image'))
                or soup.find('meta', property='og:image')
            )

            cover_url = None
            issue_filename = ""
            if img:
                raw_src = img.get('content') or img.get('src') or ''
                if raw_src.startswith('//'):
                    raw_src = 'https:' + raw_src
                elif raw_src.startswith('/'):
                    raw_src = urljoin(base_url, raw_src)

                # Upgrade to high-res thumbnail (fthumb250x350)
                cover_url = re.sub(r'/fthumb\d+x\d+/', '/fthumb250x350/', raw_src)
                issue_filename = raw_src.split('/')[-1]

            # Price
            price = None
            price_el = soup.find(class_=re.compile(r'price'))
            if price_el:
                price_num = price_el.get_text(strip=True)
                if price_num:
                    price = f"{price_num} kr"

            # Detect issue number from image filename or title
            # e.g. "kalle-anka--co-32-2026.jpg" -> 32 / 2026
            # e.g. "kalle-ankas-pocket-586-2026.jpg" -> 586
            title = page_title
            issue_path = pub_code

            if m_img := re.search(r'([a-z0-9-]+?)-(\d+)-(\d{4})', issue_filename, re.I):
                issue_num = int(m_img.group(2))
                issue_year = int(m_img.group(3))
                if pub_code == "se/KA":
                    title = f"Kalle Anka & C:o nr {issue_num}/{issue_year}"
                    issue_path = f"se/KA{issue_year}-{issue_num:02d}"
                elif pub_code == "se/KAP":
                    title = f"Kalle Ankas Pocket nr {issue_num}"
                    issue_path = f"se/KAP  {issue_num}"
                else:
                    title = f"{page_title} nr {issue_num}/{issue_year}"
            elif m_cap := re.search(r'(\d+)', issue_filename):
                title = f"{page_title} nr {m_cap.group(1)}"

            book_id = issue_filename.replace('.jpg', '').replace('.png', '') or path.strip('/')
            if book_id in seen:
                continue
            seen.add(book_id)

            result.append({
                "id": book_id,
                "title": title,
                "url": url,
                "price": price,
                "cover_url": cover_url,
                "date": None,
                "released": True,
                "publisher": "Story House Egmont",
                "issue_path": issue_path
            })

        except Exception as e:
            print(f"  [warn] discover_se failed for {path}: {e}")

    return result

def fetch_se_details(url: str) -> dict:
    return {}
