#!/usr/bin/env python3
"""
Disney Comics Agenda - Data Exporter
Extracts all comic releases from DBI files and scrapers into a clean, normalized releases.json
for the minimalist agenda web application.
"""

import os
import re
import sys
import json
import subprocess
from datetime import datetime, date
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")

COUNTRY_INFO = {
    "fr": {"name": "France", "flag": "🇫🇷"},
    "it": {"name": "Italy", "flag": "🇮🇹"},
    "de": {"name": "Germany", "flag": "🇩🇪"},
    "us": {"name": "United States", "flag": "🇺🇸"},
    "gr": {"name": "Greece", "flag": "🇬🇷"},
    "br": {"name": "Brazil", "flag": "🇧🇷"},
    "bg": {"name": "Bulgaria", "flag": "🇧🇬"},
    "cz": {"name": "Czech Republic", "flag": "🇨🇿"},
    "es": {"name": "Spain", "flag": "🇪🇸"},
    "fi": {"name": "Finland", "flag": "🇫🇮"},
    "nl": {"name": "Netherlands", "flag": "🇳🇱"},
    "dk": {"name": "Denmark", "flag": "🇩🇰"},
    "no": {"name": "Norway", "flag": "🇳🇴"},
    "se": {"name": "Sweden", "flag": "🇸🇪"},
    "pl": {"name": "Poland", "flag": "🇵🇱"},
    "eg": {"name": "Egypt", "flag": "🇪🇬"},
    "is": {"name": "Iceland", "flag": "🇮🇸"},
    "hr": {"name": "Croatia", "flag": "🇭🇷"},
    "ee": {"name": "Estonia", "flag": "🇪🇪"},
    "lv": {"name": "Latvia", "flag": "🇱🇻"},
    "lt": {"name": "Lithuania", "flag": "🇱🇹"},
    "rs": {"name": "Serbia", "flag": "🇷🇸"},
    "si": {"name": "Slovenia", "flag": "🇸🇮"},
    "uk": {"name": "United Kingdom", "flag": "🇬🇧"},
    "cn": {"name": "China", "flag": "🇨🇳"},
    "mx": {"name": "Mexico", "flag": "🇲🇽"},
    "tr": {"name": "Turkey", "flag": "🇹🇷"},
}

RAW_COVERS_BASE = "https://raw.githubusercontent.com/WizyxGH/disney-comics-watcher/datas/covers/"

def parse_date_str(val):
    if not val:
        return None
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    val = str(val).strip()
    # YYYY-MM-DD
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', val)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r'^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$', val)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    # Month Year or other formats
    return None

def format_english_date(iso_date):
    if not iso_date:
        return ""
    months = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d").date()
        day_name = days[dt.weekday()]
        return f"{day_name}, {months[dt.month]} {dt.day}, {dt.year}"
    except Exception:
        return iso_date

def get_cover_filename(issue_code: str, country: str) -> str:
    from src.utils import cover_filename
    return cover_filename(issue_code, country)

def parse_dbi_content(content: str, country: str) -> list[dict]:
    """Parses a .dbi file into list of release dicts."""
    results = []
    lines = content.splitlines()
    for line in lines:
        if " h3 " not in line:
            continue
        parts = line.split(" h3 ", 1)
        issue_code = parts[0].strip()
        rest = parts[1].strip()

        # extract [issdate:...], [price:...], [pages:...], [size:...], [EAN ...]
        issdate = None
        m_date = re.search(r'\[issdate:([^\]]+)\]', rest)
        if m_date:
            issdate = parse_date_str(m_date.group(1))
        else:
            # Try inferring year & month from issue code / title (e.g. DS2026-05, MAC2026-07, 05/2026)
            m_ym = re.search(r'(202\d)[/-](\d{1,2})|(\d{1,2})[/-](202\d)', f"{issue_code} {rest}")
            if m_ym:
                y = m_ym.group(1) or m_ym.group(4)
                m = m_ym.group(2) or m_ym.group(3)
                try:
                    m_int = int(m)
                    if 1 <= m_int <= 12:
                        issdate = f"{y}-{m_int:02d}-01"
                except Exception:
                    pass

        price = None
        m_price = re.search(r'\[price:([^\]]+)\]', rest)
        if m_price:
            price = m_price.group(1).strip()

        pages = None
        m_pages = re.search(r'\[pages:([^\]]+)\]', rest)
        if m_pages:
            pages = m_pages.group(1).strip()

        ean = None
        m_ean = re.search(r'\[EAN\s+([^\]]+)\]', rest)
        if m_ean:
            ean = m_ean.group(1).strip()

        # Clean title
        title = re.sub(r'\[[^\]]+\]', '', rest).strip()

        c_info = COUNTRY_INFO.get(country, {"name": country.upper(), "flag": "🌐"})
        cover_fn = get_cover_filename(issue_code, country) + ".jpg"
        cover_url = f"{RAW_COVERS_BASE}{cover_fn}"

        results.append({
            "id": f"{country}_{issue_code.replace(' ', '_')}",
            "issue_code": issue_code,
            "title": title or issue_code,
            "country": country,
            "country_name": c_info["name"],
            "country_flag": c_info["flag"],
            "date": issdate,
            "formatted_date": format_english_date(issdate) if issdate else None,
            "price": price,
            "pages": pages,
            "ean": ean,
            "cover_url": cover_url,
            "url": f"https://inducks.org/issue.php?c={country}%2F{issue_code.replace(' ', '+')}",
            "source": "dbi"
        })
    return results

def load_dbi_releases() -> list[dict]:
    """Loads releases from local issues/ or git show origin/datas:issues/."""
    releases = []
    dbi_files = [f"{c}.dbi" for c in COUNTRY_INFO.keys()]

    for dbi_file in dbi_files:
        country = dbi_file.split(".")[0]
        local_path = os.path.join("issues", dbi_file)
        content = None
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            try:
                cmd = ["git", "show", f"origin/datas:issues/{dbi_file}"]
                content = subprocess.check_output(cmd, text=True, encoding="utf-8", stderr=subprocess.DEVNULL)
            except Exception:
                pass
        if content:
            parsed = parse_dbi_content(content, country)
            releases.extend(parsed)
    return releases

def discover_from_scrapers() -> list[dict]:
    """Runs key scrapers to fetch upcoming and recent releases."""
    import concurrent.futures

    scrapers = []
    try:
        from src.scrapers.fr import discover_glenat, discover_fr_kiosk
        scrapers.append(("fr", "Glénat", discover_glenat))
        scrapers.append(("fr", "Kiosque Presse", discover_fr_kiosk))
    except Exception as e:
        print(f"  [warn] scrapers.fr: {e}")

    try:
        from src.scrapers.it import discover_panini_it
        scrapers.append(("it", "Panini Comics", discover_panini_it))
    except Exception as e:
        print(f"  [warn] scrapers.it: {e}")

    try:
        from src.scrapers.de import discover_lustiges_taschenbuch_de, fetch_lustiges_taschenbuch_de_details
        def get_ltb_with_dates():
            b_list = discover_lustiges_taschenbuch_de()
            def fetch_single(b):
                if b.get("url"):
                    det = fetch_lustiges_taschenbuch_de_details(b["url"])
                    if det.get("date"):
                        b["date"] = det["date"]
                    if det.get("name") and " - " not in b["title"]:
                        b["title"] += f" - {det['name']}"
                return b
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ltb_ex:
                return list(ltb_ex.map(fetch_single, b_list))
        scrapers.append(("de", "Egmont LTB", get_ltb_with_dates))
    except Exception as e:
        print(f"  [warn] scrapers.de LTB: {e}")

    try:
        from src.scrapers.us import discover_dynamite, discover_marvel, fetch_marvel_details
        def get_marvel_with_dates():
            m_list = discover_marvel()
            for b in m_list:
                if b.get("url"):
                    det = fetch_marvel_details(b["url"])
                    if det.get("date"):
                        b["date"] = det["date"]
            return m_list
        scrapers.append(("us", "Dynamite Entertainment", discover_dynamite))
        scrapers.append(("us", "Marvel Comics", get_marvel_with_dates))
    except Exception as e:
        print(f"  [warn] scrapers.us: {e}")

    try:
        from src.scrapers.gr import discover_kathimerini
        scrapers.append(("gr", "Kathimerini", discover_kathimerini))
    except Exception as e:
        print(f"  [warn] scrapers.gr: {e}")

    try:
        from src.scrapers.mx import discover_panini_mx
        scrapers.append(("mx", "Panini Comics México", discover_panini_mx))
    except Exception as e:
        print(f"  [warn] scrapers.mx: {e}")

    try:
        from src.scrapers.tr import discover_tr
        scrapers.append(("tr", "Beta Kids", discover_tr))
    except Exception as e:
        print(f"  [warn] scrapers.tr: {e}")

    try:
        from src.scrapers.hr import discover_hr
        scrapers.append(("hr", "Egmont Hrvatska", discover_hr))
    except Exception as e:
        print(f"  [warn] scrapers.hr: {e}")

    try:
        from src.scrapers.rs import discover_rs
        scrapers.append(("rs", "Egmont Srbija", discover_rs))
    except Exception as e:
        print(f"  [warn] scrapers.rs: {e}")

    try:
        from src.scrapers.lt import discover_lt
        scrapers.append(("lt", "Egmont Lietuva", discover_lt))
    except Exception as e:
        print(f"  [warn] scrapers.lt: {e}")

    try:
        from src.scrapers.se import discover_se
        scrapers.append(("se", "Story House Egmont", discover_se))
    except Exception as e:
        print(f"  [warn] scrapers.se: {e}")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(scrapers) or 1) as ex:
        futs = {ex.submit(fn): (cc, pub) for cc, pub, fn in scrapers}
        for fut in concurrent.futures.as_completed(futs):
            cc, pub = futs[fut]
            try:
                books = fut.result()
                c_info = COUNTRY_INFO.get(cc, {"name": cc.upper(), "flag": "🌐"})
                for b in books:
                    raw_date = b.get("date") or b.get("date_mise_en_vente") or b.get("pub_date")
                    iso_date = parse_date_str(raw_date)
                    ean = b.get("ean") or b.get("sku") or b.get("id")
                    title = b.get("title") or "Titre inconnu"
                    cover = b.get("cover_url") or b.get("image")
                    url = b.get("url")
                    price = b.get("price")

                    results.append({
                        "id": f"{cc}_{ean or title.lower().replace(' ', '_')[:30]}",
                        "issue_code": b.get("issue_code"),
                        "title": title,
                        "country": cc,
                        "country_name": c_info["name"],
                        "country_flag": c_info["flag"],
                        "publisher": pub,
                        "date": iso_date,
                        "formatted_date": format_english_date(iso_date) if iso_date else None,
                        "price": price,
                        "pages": b.get("pages"),
                        "ean": ean,
                        "cover_url": cover,
                        "url": url,
                        "source": "scraper"
                    })
            except Exception as e:
                print(f"  [warn] Scraper {pub} failed: {e}")
    return results

def build_agenda(output_path="web/data/releases.json"):
    today_str = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
    print(f"[Agenda] Generating agenda as of {today_str}...")

    dbi_releases = load_dbi_releases()
    print(f"  Loaded {len(dbi_releases)} releases from DBI files.")

    scraper_releases = discover_from_scrapers()
    print(f"  Loaded {len(scraper_releases)} releases from live scrapers.")

    # Merge and deduplicate
    # Strategy: group by country + normalized title / ean
    all_releases = []
    seen_keys = set()

    # Prioritize scraper releases (they often have direct links and store covers)
    # followed by dbi releases
    combined = scraper_releases + dbi_releases

    for item in combined:
        title = item.get("title", "").strip().lower()
        country = item.get("country", "")
        ean = str(item.get("ean") or "")
        dt = item.get("date") or ""

        # unique key
        key = f"{country}:{ean}" if len(ean) > 6 else f"{country}:{title[:25]}:{dt}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        # compute status
        if dt:
            item["status"] = "released" if dt <= today_str else "upcoming"
        else:
            item["status"] = "upcoming"

        all_releases.append(item)

    # Sort: Releases with date sorted descending/ascending.
    # We sort by date descending so recent/future releases are at the top, or by date
    def sort_key(x):
        d = x.get("date")
        if not d:
            return "0000-00-00"
        return d

    all_releases.sort(key=sort_key, reverse=True)

    # Country statistics
    country_counts = {}
    for r in all_releases:
        c = r["country"]
        country_counts[c] = country_counts.get(c, 0) + 1

    payload = {
        "generated_at": datetime.now(PARIS_TZ).isoformat(),
        "total_count": len(all_releases),
        "countries": [
            {
                "code": code,
                "name": COUNTRY_INFO.get(code, {}).get("name", code.upper()),
                "flag": COUNTRY_INFO.get(code, {}).get("flag", "🌐"),
                "count": country_counts.get(code, 0)
            }
            for code in sorted(country_counts.keys(), key=lambda c: -country_counts[c])
        ],
        "releases": all_releases
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[Agenda] Successfully exported {len(all_releases)} releases to {output_path}")
    return payload

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "web/data/releases.json"
    build_agenda(out_file)
