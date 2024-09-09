import os
import shutil
import argparse
import rumps
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from utils import (get_or_initialize_git_repo, ensure_branches_for_directories, apply_ignore_rule_to_all_branches,
                   delete_main_branch, get_syft_config, check_or_create_keypair,
                   navigate_to_root_datasite_and_ensure_syftperm_files_tracked, navigate_to_root_datasite_and_commit_changes,
                   create_and_apply_patches_for_new_files)


class OutboxHandler(FileSystemEventHandler):
    def __init__(self, server_url, target_user):
        super().__init__()
        self.server_url = server_url
        self.target_user = target_user

    def on_created(self, event):
        if not event.is_directory:
            self.upload_file(event.src_path)

    def upload_file(self, file_path):
        try:
            filepath = os.path.relpath(file_path)
            with open(file_path, 'rb') as f:
                response = requests.post(f'{self.server_url}/upload', 
                                         files={'file': f},
                                         data={'target_user': self.target_user,
                                               'filepath': filepath})
                if response.status_code == 200:
                    print(f"Uploaded file: {file_path}")
                else:
                    print(f"Failed to upload {file_path}: {response.text}")
        except Exception as e:
            print(f"Error uploading file {file_path}: {e}")


class SyftBox(rumps.App):
    def __init__(self, folder_path=None, datasite=None):
        self.folder_path = folder_path
        self.datasite = datasite

        self.known_users = set()
        
        # if not self.folder_path:
        self.config_folder()

        # if not self.datasite:
        self.config_datasite()
        
        self.repo = get_or_initialize_git_repo(self.folder_path)
        self.update_branches()
        delete_main_branch(self.repo)
        get_syft_config(self.repo, self.datasite)
        check_or_create_keypair(self.repo, self.datasite)
        navigate_to_root_datasite_and_ensure_syftperm_files_tracked(self.repo)
        navigate_to_root_datasite_and_commit_changes(self.repo)
        create_and_apply_patches_for_new_files(self.repo, outbox_dir=os.path.join(self.folder_path, "outbox"))

        # Initialize the app with the selected folder and icon
        super(SyftBox, self).__init__(
            "SyftBox",
            icon="mark-primary-trans.png",
            menu=["Config"]
        )

        self.register_user()
        
        # Watch the outbox directory for new files
        self.start_watching_outbox()
        
        # Start polling the server for new users every 1 second
        rumps.timer(2)(self.check_for_new_users)
        
        # poll for patches to send every 1 second
        rumps.timer(2)(self.check_for_messages_to_send)

    def register_user(self):
        """Registers the user with the server."""
        try:
            response = requests.post(f'http://localhost:8082/register', data={'user_id': self.datasite})
            if response.status_code in (200, 201):
                print(f"User {self.datasite} registered successfully.")
            else:
                print(f"Failed to register user {self.datasite}: {response.text}")
        except Exception as e:
            print(f"Error registering user {self.datasite}: {e}")

    def check_for_messages_to_send(self, _):
        print("\n")
        ensure_branches_for_directories(self.repo)
        navigate_to_root_datasite_and_ensure_syftperm_files_tracked(self.repo)
        navigate_to_root_datasite_and_commit_changes(self.repo)
        create_and_apply_patches_for_new_files(self.repo,
                                               outbox_dir=os.path.join(self.folder_path,
                                                                       "outbox"))

            
    def check_for_new_users(self, _):
        """Checks for new users on the server and creates folders for them."""
        try:
            response = requests.get(f'http://localhost:8082/users')
            if response.status_code == 200:
                users = set(response.json())
                new_users = users - self.known_users
                if new_users:
                    print(f"New users detected: {new_users}")
                    for user in new_users:
                        user_folder = os.path.join(self.folder_path, user)
                        os.makedirs(user_folder, exist_ok=True)
                        print(f"Created folder for new user: {user}")

                    # Update the known_users set with the new users
                    self.known_users.update(new_users)
                else:
                    print("No new users detected.")
            else:
                print(f"Failed to fetch users: {response.text}")
        except Exception as e:
            print(f"Error checking for new users: {e}")            
            
    def start_watching_outbox(self):
        outbox_path = os.path.join(self.folder_path, "outbox")
        if not os.path.exists(outbox_path):
            os.makedirs(outbox_path)

        event_handler = OutboxHandler(server_url="http://localhost:8082", target_user=self.datasite)
        observer = Observer()
        observer.schedule(event_handler, path=outbox_path, recursive=False)
        observer.start()

        print(f"Started watching the outbox at: {outbox_path}")        
        
    def start_watching_outbox(self):
        outbox_path = os.path.join(self.folder_path, "outbox")
        if not os.path.exists(outbox_path):
            os.makedirs(outbox_path)

        event_handler = OutboxHandler(server_url="http://localhost:8082", target_user=self.datasite)
        observer = Observer()
        observer.schedule(event_handler, path=outbox_path, recursive=False)
        observer.start()

        print(f"Started watching the outbox at: {outbox_path}")

    def update_branches(self):
        ensure_branches_for_directories(self.repo)
        apply_ignore_rule_to_all_branches(repo=self.repo,
                                          postfix='.patch',
                                          path=self.folder_path)
        apply_ignore_rule_to_all_branches(repo=self.repo,
                                          postfix='outbox',
                                          path=self.folder_path)
        apply_ignore_rule_to_all_branches(repo=self.repo,
                                          postfix='.DS_Store',
                                          path=self.folder_path)

    def config_datasite(self):
        if not self.datasite:
            datasite = rumps.Window(
                title="Choose Datasite",
                message="Please specify the name of your datasite:",
                default_text="andrew@syft_cache.org",
                ok="Confirm",
                cancel="Cancel",
                dimensions=(320, 20)
            ).run()

            # If the user cancels, exit the application
            if not datasite.clicked:
                rumps.alert("No datasite specified. Exiting application.")
                rumps.quit_application()

            self.datasite = os.path.expanduser(datasite.text)
        self.datasite_path = os.path.join(self.folder_path, self.datasite)

        # Create the folder if it doesn't exist
        if not os.path.exists(self.datasite_path):
            os.makedirs(self.datasite_path)

    def config_folder(self):
        if not self.folder_path:
            # Ask the user to confirm or specify the folder to use
            default_folder = os.path.expanduser("~/SyftBox/")
            folder = rumps.Window(
                title="Choose Folder",
                message="Please confirm the folder to use (default is ~/SyftBox/):",
                default_text=default_folder,
                ok="Confirm",
                cancel="Cancel",
                dimensions=(320, 20)
            ).run()

            # If the user cancels, exit the application
            if not folder.clicked:
                rumps.alert("No folder selected. Exiting application.")
                rumps.quit_application()

            self.folder_path = os.path.expanduser(folder.text)

        # Delete the folder if it already exists
        if os.path.exists(self.folder_path):
            try:
                shutil.rmtree(self.folder_path)
                print(f"Deleted existing folder: {self.folder_path}")
            except Exception as e:
                rumps.alert(f"Error deleting folder: {e}")
                rumps.quit_application()

        # Create the folder afresh
        os.makedirs(self.folder_path)

    @rumps.clicked("Config")
    def say_hello(self, _):
        rumps.alert(f"Using folder: {self.folder_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SyftBox App")
    parser.add_argument('--folder_path', type=str, help='Path to the folder to use')
    parser.add_argument('--datasite', type=str, help='Datasite name to use')

    args = parser.parse_args()

    SyftBox(folder_path=args.folder_path, datasite=args.datasite).run()
