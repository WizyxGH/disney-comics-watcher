import os
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_URL = os.environ.get("TURSO_DATABASE_URL", "").replace("libsql://", "https://")
AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

_HEADERS = None


def _get_headers():
    global _HEADERS
    if _HEADERS is None:
        if not DB_URL or not AUTH_TOKEN:
            return None
        _HEADERS = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Content-Type": "application/json",
        }
    return _HEADERS


def query_db(query: str, params: tuple = ()):
    """Executes a SQL query against the Turso database via HTTP API."""
    headers = _get_headers()
    if not headers:
        print("[WARNING] TURSO_DATABASE_URL and/or TURSO_AUTH_TOKEN not set. Database queries will be disabled.")
        return []

    args = []
    for p in params:
        if p is None:
            args.append({"type": "null"})
        elif isinstance(p, int):
            args.append({"type": "integer", "value": str(p)})
        elif isinstance(p, float):
            args.append({"type": "float", "value": str(p)})
        else:
            args.append({"type": "text", "value": str(p)})

    payload = {
        "requests": [
            {"type": "execute", "stmt": {"sql": query, "args": args}},
            {"type": "close"},
        ]
    }

    try:
        r = requests.post(f"{DB_URL}/v2/pipeline", headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        result = data["results"][0]
        if result["type"] == "error":
            print(f"[DB ERROR] {result['error']['message']}")
            return []
        rows_raw = result["response"]["result"]["rows"]
        # Return as list of tuples (same interface as before)
        return [tuple(cell.get("value") for cell in row) for row in rows_raw]
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return []


def execute_db(query: str, params: tuple = ()):
    """Executes a non-SELECT SQL statement (CREATE, INSERT, etc.)."""
    headers = _get_headers()
    if not headers:
        return False

    args = []
    for p in params:
        if p is None:
            args.append({"type": "null"})
        elif isinstance(p, int):
            args.append({"type": "integer", "value": str(p)})
        elif isinstance(p, float):
            args.append({"type": "float", "value": str(p)})
        else:
            args.append({"type": "text", "value": str(p)})

    payload = {
        "requests": [
            {"type": "execute", "stmt": {"sql": query, "args": args}},
            {"type": "close"},
        ]
    }

    try:
        r = requests.post(f"{DB_URL}/v2/pipeline", headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        result = data["results"][0]
        if result["type"] == "error":
            print(f"[DB ERROR] {result['error']['message']}")
            return False
        return True
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return False


def execute_batch(statements: list[dict]):
    """Executes multiple SQL statements in a single HTTP call.
    Each item in statements: {'sql': '...', 'args': [...]} or just a string.
    """
    headers = _get_headers()
    if not headers:
        return False

    requests_list = []
    for stmt in statements:
        if isinstance(stmt, str):
            requests_list.append({"type": "execute", "stmt": {"sql": stmt}})
        else:
            requests_list.append({"type": "execute", "stmt": stmt})
    requests_list.append({"type": "close"})

    payload = {"requests": requests_list}
    try:
        r = requests.post(f"{DB_URL}/v2/pipeline", headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        errors = [res["error"]["message"] for res in data["results"] if res["type"] == "error"]
        if errors:
            for e in errors[:5]:
                print(f"[DB ERROR] {e}")
            return False
        return True
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return False
