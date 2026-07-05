import os
import sys
import libsql_client

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_URL = os.environ.get("TURSO_DATABASE_URL")
AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

_client = None

def get_db_client():
    global _client
    if _client is not None:
        return _client

    if not DB_URL or not AUTH_TOKEN:
        print("[ERROR] TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set in .env")
        sys.exit(1)

    try:
        _client = libsql_client.create_client_sync(url=DB_URL, auth_token=AUTH_TOKEN)
        return _client
    except Exception as e:
        print(f"[ERROR] Failed to connect to Turso database: {e}")
        sys.exit(1)

def query_db(query: str, params: tuple = ()):
    client = get_db_client()
    rs = client.execute(query, params)
    return rs.rows
