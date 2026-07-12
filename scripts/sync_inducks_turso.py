import os
import sys
import tarfile
import tempfile
import requests
import csv
import io
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.db import execute_batch, query_db

INDUCKS_TGZ_URL = "https://inducks.org/bld/isv.tgz"

def download_and_extract(url, extract_to):
    print(f"Downloading {url}...")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    print("Download complete. Extracting...")
    with tarfile.open(fileobj=io.BytesIO(r.content), mode="r:gz") as tar:
        tar.extractall(path=extract_to)
    print(f"Extracted to {extract_to}")

def sync_table(filepath: Path, table_name: str):
    print(f"Syncing table {table_name} from {filepath.name}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='^', quoting=csv.QUOTE_NONE)
        header = next(reader)
        if not header:
            print("Empty file")
            return
            
        # Get schema from Turso
        schema = query_db(f"PRAGMA table_info({table_name})")
        if not schema:
            print(f"Table {table_name} not found in Turso")
            return
            
        valid_columns = [col[1] for col in schema]
        
        # Find indices of valid columns in the CSV
        col_indices = []
        for i, col in enumerate(header):
            if col in valid_columns:
                col_indices.append((i, col))
                
        if not col_indices:
            print(f"No matching columns for {table_name}")
            return
            
        columns = [c[1] for c in col_indices]
        placeholders = ", ".join(["?" for _ in columns])
        sql = f"INSERT OR REPLACE INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
        
        batch = []
        batch_size = 5000
        total = 0
        
        for row in reader:
            # Extract only the valid columns
            row_vals = []
            for idx, _ in col_indices:
                if idx < len(row):
                    row_vals.append(row[idx])
                else:
                    row_vals.append(None)
                    
            # Handle empty strings and None properly for the DB
            args = []
            for val in row_vals:
                if val is None or val == "":
                    args.append({"type": "null"})
                else:
                    args.append({"type": "text", "value": str(val)})
            
            batch.append({"sql": sql, "args": args})
            
            if len(batch) >= batch_size:
                if not execute_batch(batch):
                    print(f"Failed to execute batch at {total}")
                total += len(batch)
                print(f"Inserted/Updated {total} rows into {table_name}...")
                batch = []
                
        if batch:
            if execute_batch(batch):
                total += len(batch)
                print(f"Inserted/Updated {total} rows into {table_name}...")
            else:
                print(f"Failed to execute final batch")
                
    print(f"Finished syncing {table_name}.")

def main():
    # Allow overriding url or local folder via arguments
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        temp_dir = sys.argv[1]
        print(f"Using local ISV directory: {temp_dir}")
        run_sync(temp_dir)
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            download_and_extract(INDUCKS_TGZ_URL, temp_dir)
            run_sync(temp_dir)

def run_sync(temp_dir):
    temp_path = Path(temp_dir)
    tables_to_sync = {
        "inducks_issue.isv": "inducks_issue"
    }
    for filename, table_name in tables_to_sync.items():
        file_path = temp_path / filename
        if file_path.exists():
            sync_table(file_path, table_name)
        else:
            print(f"Warning: {filename} not found in {temp_dir}")

if __name__ == "__main__":
    main()
