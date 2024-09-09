import os
import hashlib
import time
import requests
import logging
import sqlite3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Dict, List

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = 5000  # Run every 5 seconds
DESCRIPTION = "A plugin that syncs files between the SyftBox directory and the cache server."

CACHE_SERVER_URL = "http://127.0.0.1:5000"  # Adjust this to your cache server's address

class ChangeLogEntry:
    def __init__(self, filename: str, hash: str, modified: float, operation: str):
        self.filename = filename
        self.hash = hash
        self.modified = modified
        self.operation = operation

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, db_path, syftbox_folder):
        self.db_path = db_path
        self.syftbox_folder = syftbox_folder

    def on_modified(self, event):
        if not event.is_directory:
            self.update_file_timestamp(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self.update_file_timestamp(event.src_path)

    def update_file_timestamp(self, file_path):
        rel_path = os.path.relpath(file_path, self.syftbox_folder)
        timestamp = os.path.getmtime(file_path)
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO file_timestamps
                         (relative_path, timestamp) VALUES (?, ?)''',
                      (rel_path, timestamp))

def init_db(db_path):
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS file_timestamps
                     (relative_path TEXT PRIMARY KEY, timestamp REAL)''')

def get_file_hash(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def get_server_changes(last_sync_time: float) -> List[ChangeLogEntry]:
    response = requests.get(f"{CACHE_SERVER_URL}/changelog/{last_sync_time}")
    response.raise_for_status()
    return [ChangeLogEntry(**entry) for entry in response.json()]

def get_server_files() -> Dict[str, Dict]:
    response = requests.get(f"{CACHE_SERVER_URL}/files")
    response.raise_for_status()
    return response.json()

def get_local_files(syftbox_folder: str, db_path: str) -> Dict[str, Dict]:
    local_files = {}
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        for root, _, files in os.walk(syftbox_folder):
            for filename in files:
                if filename.startswith('.') or filename.endswith('.syftperm'):
                    continue
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, syftbox_folder)
                file_hash = get_file_hash(file_path)
                c.execute('SELECT timestamp FROM file_timestamps WHERE relative_path = ?', (rel_path,))
                result = c.fetchone()
                timestamp = result[0] if result else os.path.getmtime(file_path)
                local_files[rel_path] = {
                    'hash': file_hash,
                    'modified': timestamp
                }
                # Update the database if the file is not there or has a different hash
                c.execute('''INSERT OR REPLACE INTO file_timestamps
                             (relative_path, timestamp) VALUES (?, ?)''',
                          (rel_path, timestamp))
    return local_files

def download_file(file_path: str, syftbox_folder: str, db_path: str, server_timestamp: float):
    response = requests.get(f"{CACHE_SERVER_URL}/files/{file_path}")
    response.raise_for_status()
    local_path = os.path.join(syftbox_folder, file_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, 'wb') as f:
        f.write(response.content)
    # Update the local timestamp to match the server's timestamp
    os.utime(local_path, (server_timestamp, server_timestamp))
    # Update the database
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO file_timestamps
                     (relative_path, timestamp) VALUES (?, ?)''',
                  (file_path, server_timestamp))
    logger.info(f"Downloaded: {file_path}")

def upload_file(file_path: str, syftbox_folder: str):
    local_path = os.path.join(syftbox_folder, file_path)
    with open(local_path, 'rb') as f:
        files = {'file': f}
        response = requests.put(f"{CACHE_SERVER_URL}/files/{file_path}", files=files)
    response.raise_for_status()
    logger.info(f"Uploaded: {file_path}")

def delete_local_file(file_path: str, syftbox_folder: str, db_path: str):
    local_path = os.path.join(syftbox_folder, file_path)
    if os.path.exists(local_path):
        os.remove(local_path)
        # Remove from database
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM file_timestamps WHERE relative_path = ?', (file_path,))
        logger.info(f"Deleted locally: {file_path}")

def delete_server_file(file_path: str):
    response = requests.delete(f"{CACHE_SERVER_URL}/files/{file_path}")
    response.raise_for_status()
    logger.info(f"Deleted on server: {file_path}")

def run(shared_state):
    global observer
    syftbox_folder = shared_state.get('syftbox_folder')
    if not syftbox_folder:
        logger.warning("syftbox_folder is not set in shared state")
        return

    db_path = os.path.join(syftbox_folder, '.sync_metadata.db')
    init_db(db_path)

    # Set up file watcher
    event_handler = FileChangeHandler(db_path, syftbox_folder)
    observer = Observer()
    observer.schedule(event_handler, syftbox_folder, recursive=True)
    observer.start()

    try:
        server_changes = get_server_changes(0)  # Get all changes
        server_files = get_server_files()
        local_files = get_local_files(syftbox_folder, db_path)

        # Handle server changes
        for change in server_changes:
            if change.operation == 'delete':
                delete_local_file(change.filename, syftbox_folder, db_path)
            elif change.operation in ['create', 'update']:
                local_info = local_files.get(change.filename)
                if not local_info or local_info['hash'] != change.hash:
                    download_file(change.filename, syftbox_folder, db_path, change.modified)
        
        # Check for new or modified local files
        for file_path, info in local_files.items():
            server_info = server_files.get(file_path)
            if not server_info or info['hash'] != server_info['hash']:
                if not server_info or info['modified'] > server_info['modified']:
                    upload_file(file_path, syftbox_folder)
        
        # Check for files deleted locally
        for file_path in server_files:
            if file_path not in local_files:
                delete_server_file(file_path)

        logger.info("Sync completed successfully")
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}")
    finally:
        observer.stop()
        observer.join()

def stop():
    global observer
    if observer:
        observer.stop()
        observer.join()
        logger.info("File watcher stopped")

if __name__ == "__main__":
    # This block is for testing the plugin independently
    class MockSharedState:
        def get(self, key):
            return os.path.expanduser("~/Desktop/SyftBox")

    run(MockSharedState())
