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


from pathlib import Path
import sqlite3

_LOCAL_DB_PATH = None

def _get_local_sqlite_path() -> str | None:
    global _LOCAL_DB_PATH
    if _LOCAL_DB_PATH is not None:
        return _LOCAL_DB_PATH if _LOCAL_DB_PATH != "" else None

    env_p = os.environ.get("LOCAL_INDUCKS_SQLITE")
    if env_p and os.path.isfile(env_p):
        _LOCAL_DB_PATH = env_p
        return _LOCAL_DB_PATH

    candidates = [
        Path(__file__).resolve().parents[3] / "data" / "inducks-db" / "inducks.sqlite",
        Path(__file__).resolve().parents[3] / "data" / "inducks.sqlite",
        Path(__file__).resolve().parents[2] / "transcript" / "data" / "inducks-db" / "inducks.sqlite",
        Path(__file__).resolve().parents[1] / "inducks.db",
    ]
    for c in candidates:
        if c.is_file() and c.stat().st_size > 1024:
            _LOCAL_DB_PATH = str(c)
            return _LOCAL_DB_PATH

    _LOCAL_DB_PATH = ""
    return None


_LOCAL_CONN = None

def _get_local_connection():
    global _LOCAL_CONN
    if _LOCAL_CONN is not None:
        return _LOCAL_CONN
    local_db = _get_local_sqlite_path()
    if not local_db:
        return None
    try:
        uri_path = f"file:{Path(local_db).as_posix()}?mode=ro"
        _LOCAL_CONN = sqlite3.connect(uri_path, uri=True, check_same_thread=False)
        return _LOCAL_CONN
    except Exception:
        try:
            _LOCAL_CONN = sqlite3.connect(local_db, check_same_thread=False)
            return _LOCAL_CONN
        except Exception as e:
            print(f"[LOCAL DB ERROR] Cannot open {local_db}: {e}")
            return None


def _query_local_sqlite(query: str, params: tuple = ()):
    conn = _get_local_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            return cur.fetchall()
        except Exception as e:
            print(f"[LOCAL DB ERROR] {e}")
    return []


_QUERY_CACHE: dict[tuple, list] = {}


def query_db(query: str, params: tuple = ()):
    """Executes a SQL query with local-first priority (0 quota used), in-memory caching, and Turso cloud fallback."""
    cache_key = (query.strip(), params)
    if cache_key in _QUERY_CACHE:
        return _QUERY_CACHE[cache_key]

    # 1. Local-first: if local SQLite is present and FORCE_TURSO is not set, use local DB (saves 100% of Turso quota locally)
    if not os.environ.get("FORCE_TURSO"):
        local_db = _get_local_sqlite_path()
        if local_db:
            res = _query_local_sqlite(query, params)
            _QUERY_CACHE[cache_key] = res
            return res

    # 2. Remote Turso query (for CI / GitHub Actions or when explicitly forced)
    headers = _get_headers()
    if not headers:
        res = _query_local_sqlite(query, params)
        _QUERY_CACHE[cache_key] = res
        return res

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
        r = requests.post(f"{DB_URL}/v2/pipeline", headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        result = data["results"][0]
        if result["type"] == "error":
            print(f"[DB ERROR] {result['error']['message']}")
            res = _query_local_sqlite(query, params)
            _QUERY_CACHE[cache_key] = res
            return res
        rows_raw = result["response"]["result"]["rows"]
        res = [tuple(cell.get("value") for cell in row) for row in rows_raw]
        _QUERY_CACHE[cache_key] = res
        return res
    except Exception as e:
        print(f"[DB WARN] Turso unreachable ({e}) — falling back to local SQLite.")
        res = _query_local_sqlite(query, params)
        _QUERY_CACHE[cache_key] = res
        return res


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
