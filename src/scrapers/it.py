from src.scrapers.shared_panini import discover_panini_magento

def discover_panini_it():
    """Discovers Disney comics on Panini Italy."""
    url = "https://www.panini.it/shp_ita_it/fumetti/panini-disney.html"
    return discover_panini_magento(url, "IT")

def fetch_panini_it_details(url: str) -> dict:
    """Fetches additional details from the product page if needed."""
    return {}
