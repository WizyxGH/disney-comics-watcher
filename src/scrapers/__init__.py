import re
import html as html_lib
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import http.client
http.client._MAXHEADERS = 1000

from src.config import KEYWORDS, SKIP_CODIFS, BI_ISSUE_CODIFS, OVERRIDES, SEARCH_URL, SITE_BASE, MLP_FAMILIES, MLP_FAMILY_URL, MLP_URL, GLENAT_BASE, GLENAT_COLLECTION_URL, FANTAGRAPHICS_DISNEY_URL, FANTAGRAPHICS_BASE, EGMONT_DE_URLS
from src.utils import get_session, parse_date_fr, truncate_summary, format_price_fr


def get_latest_inducks_issue_number(publication_code: str) -> int:
    """Queries the Turso database to find the highest numeric issue number for a publication."""
    try:
        from src.db import query_db
        # Query the database for all issue numbers matching the publication code
        rows = query_db("SELECT issuenumber FROM inducks_issue WHERE publicationcode = ?", (publication_code,))
        
        max_num = 0
        for row in rows:
            issue_num_str = str(row[0])
            if issue_num_str and issue_num_str.isdigit():
                num = int(issue_num_str)
                if num > max_num:
                    max_num = num
        return max_num
    except Exception as e:
        print(f"  [warn] Failed to fetch latest Inducks issue number for {publication_code} from DB: {e}")
        return 0


