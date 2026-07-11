from src.scrapers.shared_panini import discover_panini_magento

def discover_es():
    """Discovers Disney comics on Panini Spain."""
    url = "https://www.panini.es/shp_esp_es/comics/disney.html"
    return discover_panini_magento(url, "ES")

def fetch_es_details(url: str) -> dict:
    """Fetches additional details from the product page if needed."""
    return {}
