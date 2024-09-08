import os
import json
import requests
import time
import hashlib

SERVER_URL = 'http://localhost:5000'
CLIENT_FOLDER = 'client_files'
CLIENT_CHANGELOG_FOLDER = 'client_changelog'
LAST_SYNC_FILE = 'last_sync.json'

for folder in [CLIENT_FOLDER, CLIENT_CHANGELOG_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def get_file_hash(file_path):
    with open(file_path, 'rb') as file:
        return hashlib.md5(file.read()).hexdigest()

def get_local_state():
    local_state = {}
    for root, dirs, files in os.walk(CLIENT_FOLDER):
        for file in files:
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, CLIENT_FOLDER)
            local_state[rel_path] = get_file_hash(path)
    return local_state

def load_last_sync():
    if os.path.exists(LAST_SYNC_FILE):
        with open(LAST_SYNC_FILE, 'r') as f:
            return json.load(f)
    return {'last_change_id': None, 'state': {}}

def save_last_sync(sync_data):
    with open(LAST_SYNC_FILE, 'w') as f:
        json.dump(sync_data, f)

def detect_local_changes(current_state, last_state):
    changes = []
    for file, file_hash in current_state.items():
        if file not in last_state or last_state[file] != file_hash:
            with open(os.path.join(CLIENT_FOLDER, file), 'rb') as f:
                content = f.read()
            changes.append({
                'type': 'MODIFY' if file in last_state else 'ADD',
                'path': file,
                'content': content.decode()
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

def apply_changes(changes):
    for change in changes:
        file_path = os.path.join(CLIENT_FOLDER, change['path'])
        if change['type'] in ['ADD', 'MODIFY']:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(change['content'].encode())
        elif change['type'] == 'DELETE':
            if os.path.exists(file_path):
                os.remove(file_path)

def save_changelog(changelog):
    for change in changelog:
        # Use the timestamp if available, otherwise use current time
        timestamp = change.get('timestamp', time.time())
        change_id = f"{timestamp}_{change['path']}"
        change_file = os.path.join(CLIENT_CHANGELOG_FOLDER, change_id)
        with open(change_file, 'w') as f:
            json.dump(change, f)

def load_local_changelog():
    changelog = []
    for filename in sorted(os.listdir(CLIENT_CHANGELOG_FOLDER)):
        with open(os.path.join(CLIENT_CHANGELOG_FOLDER, filename), 'r') as f:
            changelog.append(json.load(f))
    return changelog

def sync():
    current_state = get_local_state()
    last_sync = load_last_sync()
    
    local_changes = detect_local_changes(current_state, last_sync['state'])
    if local_changes:
        if push_changes(local_changes):
            print(f"Pushed {len(local_changes)} local changes to server")
        else:
            print("Failed to push local changes")
    
    server_changelog = get_full_changelog()
    local_changelog = load_local_changelog()
    
    if len(server_changelog) > len(local_changelog):
        new_changes = server_changelog[len(local_changelog):]
        apply_changes(new_changes)
        save_changelog(new_changes)
        print(f"Applied {len(new_changes)} new changes from server")
    
    new_sync = {
        'last_change_id': server_changelog[-1].get('timestamp', time.time()) if server_changelog else None,
        'state': get_local_state()
    }
    save_last_sync(new_sync)

if __name__ == '__main__':
    while True:
        sync()
        time.sleep(2)  # Sync every 2 seconds