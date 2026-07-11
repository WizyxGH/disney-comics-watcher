from src.scrapers.shared_panini import discover_panini_magento, fetch_panini_magento_details

def discover_panini_br():
    """Discovers Disney comics on Panini Brazil."""
    url = "https://panini.com.br/disney"
    return discover_panini_magento(url, "BR")

def fetch_panini_br_details(url: str) -> dict:
    """Fetches additional details from the product page if needed."""
    return fetch_panini_magento_details(url)
