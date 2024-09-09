import os
import json
import requests
import time
import hashlib
import logging
import shutil
from threading import Event

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = 2000  # Run every 2 seconds
DESCRIPTION = "A plugin that synchronizes files between the SyftBox folder and the cache server."

SERVER_URL = 'http://localhost:5000'
CLIENT_CHANGELOG_FOLDER = '.syft_changelog'
LAST_SYNC_FILE = 'last_sync.json'

stop_event = Event()
first_run = True

def get_file_hash(file_path):
    with open(file_path, 'rb') as file:
        return hashlib.md5(file.read()).hexdigest()

def get_local_state(syftbox_folder):
    local_state = {}
    for root, dirs, files in os.walk(syftbox_folder):
        if CLIENT_CHANGELOG_FOLDER in root:
            continue
        for file in files:
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, syftbox_folder)
            local_state[rel_path] = get_file_hash(path)
    return local_state

def load_last_sync(syftbox_folder):
    sync_file = os.path.join(syftbox_folder, CLIENT_CHANGELOG_FOLDER, LAST_SYNC_FILE)
    if os.path.exists(sync_file):
        with open(sync_file, 'r') as f:
            return json.load(f)
    return {'last_change_id': None, 'state': {}}

def save_last_sync(syftbox_folder, sync_data):
    sync_file = os.path.join(syftbox_folder, CLIENT_CHANGELOG_FOLDER, LAST_SYNC_FILE)
    os.makedirs(os.path.dirname(sync_file), exist_ok=True)
    with open(sync_file, 'w') as f:
        json.dump(sync_data, f)

def detect_local_changes(current_state, last_state, syftbox_folder):
    changes = []
    for file, file_hash in current_state.items():
        if file not in last_state or last_state[file] != file_hash:
            with open(os.path.join(syftbox_folder, file), 'rb') as f:
                content = f.read()
            changes.append({
                'type': 'MODIFY' if file in last_state else 'ADD',
                'path': file,
                'content': content.hex()  # Convert binary content to hex string
            })
    
    for file in last_state:
        if file not in current_state:
            changes.append({
                'type': 'DELETE',
                'path': file
            })
    
    return changes

def push_changes(changes):
    response = requests.post(f'{SERVER_URL}/push_changes', json={'changes': changes})
    return response.status_code == 200

def get_full_changelog():
    response = requests.get(f'{SERVER_URL}/get_full_changelog')
    return response.json()

def apply_changes(changes, syftbox_folder):
    for change in changes:
        file_path = os.path.join(syftbox_folder, change['path'])
        if change['type'] in ['ADD', 'MODIFY']:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(bytes.fromhex(change['content']))  # Convert hex string back to binary
        elif change['type'] == 'DELETE':
            if os.path.exists(file_path):
                os.remove(file_path)
                # Remove empty directories
                dir_path = os.path.dirname(file_path)
                while dir_path != syftbox_folder:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        dir_path = os.path.dirname(dir_path)
                    else:
                        break

def save_changelog(syftbox_folder, changelog):
    changelog_folder = os.path.join(syftbox_folder, CLIENT_CHANGELOG_FOLDER)
    os.makedirs(changelog_folder, exist_ok=True)
    for change in changelog:
        timestamp = change.get('timestamp', time.time())
        change_id = f"{timestamp}_{change['path'].replace('/', '_')}"
        change_file = os.path.join(changelog_folder, change_id)
        with open(change_file, 'w') as f:
            json.dump(change, f)

def load_local_changelog(syftbox_folder):
    changelog_folder = os.path.join(syftbox_folder, CLIENT_CHANGELOG_FOLDER)
    changelog = []
    if os.path.exists(changelog_folder):
        for filename in sorted(os.listdir(changelog_folder)):
            if filename != LAST_SYNC_FILE:
                with open(os.path.join(changelog_folder, filename), 'r') as f:
                    changelog.append(json.load(f))
    return changelog

def clear_syftbox_folder(syftbox_folder):
    for root, dirs, files in os.walk(syftbox_folder, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))

def sync(syftbox_folder):
    global first_run
    try:
        if first_run:
            logger.info("First run: Clearing SyftBox folder and syncing with server")
            clear_syftbox_folder(syftbox_folder)
            first_run = False

        current_state = get_local_state(syftbox_folder)
        last_sync = load_last_sync(syftbox_folder)
        
        local_changes = detect_local_changes(current_state, last_sync['state'], syftbox_folder)
        if local_changes:
            if push_changes(local_changes):
                logger.info(f"Pushed {len(local_changes)} local changes to server")
            else:
                logger.error("Failed to push local changes")
        
        server_changelog = get_full_changelog()
        local_changelog = load_local_changelog(syftbox_folder)
        
        if len(server_changelog) > len(local_changelog):
            new_changes = server_changelog[len(local_changelog):]
            apply_changes(new_changes, syftbox_folder)
            save_changelog(syftbox_folder, new_changes)
            logger.info(f"Applied {len(new_changes)} new changes from server")
        
        new_sync = {
            'last_change_id': server_changelog[-1]['timestamp'] if server_changelog else None,
            'state': get_local_state(syftbox_folder)
        }
        save_last_sync(syftbox_folder, new_sync)
    except Exception as e:
        logger.error(f"Error in sync function: {str(e)}", exc_info=True)

def run(shared_state):
    if stop_event.is_set():
        logger.info("Plugin received stop signal before starting.")
        return

    syftbox_folder = shared_state.get('syftbox_folder')
    if not syftbox_folder:
        logger.error("syftbox_folder is not set in shared state")
        return

    try:
        sync(syftbox_folder)
    except Exception as e:
        logger.error(f"Unexpected error in sync_files_with_cache: {str(e)}")

def stop():
    stop_event.set()
    logger.info("Stop signal received for sync_files_with_cache plugin.")