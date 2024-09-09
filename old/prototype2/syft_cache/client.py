import os
import shutil
import time
import requests
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

SERVER_URL = 'http://localhost:8082'
WATCH_DIRECTORY = 'client_folder'
POLL_INTERVAL = 1  # seconds

# Get USER_ID from the command line argument
if len(sys.argv) < 2:
    print("Usage: python client.py <USER_ID>")
    sys.exit(1)

USER_ID = sys.argv[1]

# Function to delete all files and outboxes in the WATCH_DIRECTORY
def clean_watch_directory():
    if os.path.exists(WATCH_DIRECTORY):
        shutil.rmtree(WATCH_DIRECTORY)
    os.makedirs(WATCH_DIRECTORY)
    print(f"Cleared all files and outboxes in {WATCH_DIRECTORY}")

# Function to create outbox folders for all users except the current client
def create_outbox_folders():
    response = requests.get(f'{SERVER_URL}/users')
    if response.status_code == 200:
        users = response.json()
        for user in users:
            if user == USER_ID:
                continue  # Skip creating an outbox for the current user

            user_outbox = os.path.join(WATCH_DIRECTORY, user)
            if not os.path.exists(user_outbox):
                os.makedirs(user_outbox)
                print(f"Created outbox folder for {user}")
    else:
        print(f"Failed to fetch user list: {response.text}")

# Upload a file to another user's outbox
def upload_file(file_path, relative_path, target_user):
    with open(file_path, 'rb') as f:
        response = requests.post(f'{SERVER_URL}/upload', files={'file': f}, data={'filepath': relative_path, 'target_user': target_user})
        if response.status_code == 200:
            print(f"Uploaded {relative_path} to {target_user}'s outbox successfully.")
        else:
            print(f"Failed to upload {relative_path} to {target_user}'s outbox: {response.text}")

# Download a file from the client's outbox
def download_file(filepath):
    response = requests.get(f'{SERVER_URL}/download/{USER_ID}/{filepath}')
    if response.status_code == 200:
        full_path = os.path.join(WATCH_DIRECTORY, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded {filepath} successfully.")
    else:
        print(f"Failed to download {filepath}: {response.text}")

# Sync the client's outbox with the server
def sync_with_server():
    # Get the list of files and their sizes from the client's outbox on the server
    response = requests.get(f'{SERVER_URL}/files/{USER_ID}')
    if response.status_code == 200:
        server_files = response.json()
        local_files = {}
        
        for root, dirs, files in os.walk(WATCH_DIRECTORY):
            for file in files:
                relative_path = os.path.relpath(os.path.join(root, file), WATCH_DIRECTORY)
                local_files[relative_path] = os.path.getsize(os.path.join(root, file))

        # Download files from the server that are new or updated
        def download_directory(storage, path_prefix=''):
            for name, content in storage.items():
                current_path = os.path.join(path_prefix, name).replace('\\', '/')
                if isinstance(content, dict):
                    download_directory(content, current_path)
                elif current_path not in local_files or local_files[current_path] != content:
                    download_file(current_path)

        download_directory(server_files)
    else:
        print(f"Failed to sync with server: {response.text}")

# Watchdog event handler for directory changes
class Watcher(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            relative_path = os.path.relpath(event.src_path, WATCH_DIRECTORY)
            target_user = relative_path.split('/')[0]  # Assumes the top folder in WATCH_DIRECTORY is the target user's name
            upload_file(event.src_path, '/'.join(relative_path.split('/')[1:]), target_user)

    def on_modified(self, event):
        if not event.is_directory:
            relative_path = os.path.relpath(event.src_path, WATCH_DIRECTORY)
            target_user = relative_path.split('/')[0]  # Assumes the top folder in WATCH_DIRECTORY is the target user's name
            upload_file(event.src_path, '/'.join(relative_path.split('/')[1:]), target_user)

if __name__ == "__main__":
    # Clean up all files and outboxes in the watch directory
    clean_watch_directory()
    
    # Set up directory watcher
    observer = Observer()
    event_handler = Watcher()
    observer.schedule(event_handler, path=WATCH_DIRECTORY, recursive=True)
    observer.start()

    try:
        while True:
            create_outbox_folders()  # Ensure all outbox folders exist except the client's own outbox
            sync_with_server()
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
