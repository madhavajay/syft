import argparse
import os
import subprocess
import sys

from ..lib import ClientConfig

config_path = os.environ.get(
    "SYFTBOX_CLIENT_CONFIG_PATH", os.path.expanduser("~/.syftbox/client_config.json")
)


def is_git_installed():
    try:
        subprocess.run(
            ["git", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def clone_repository(repo_url, clone_dir):
    try:
        subprocess.run(["git", "clone", repo_url, clone_dir], check=True)
        print(f"Repository cloned into {clone_dir}")
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e}")


def main() -> None:
    client_config = ClientConfig.load(config_path)
    parser = argparse.ArgumentParser(description="Install syftbox app.")
    parser.add_argument("app", type=str, help="App repository name.")

    args = parser.parse_args()

    if is_git_installed():
        repo_url = f"https://github.com/{args.app}.git"
        clone_dir = f"{str(client_config.sync_folder)}/apps/{args.app.split('/')[-1]}"
        clone_repository(repo_url, clone_dir)
    else:
        print("Git is not installed. Please install Git and try again.")
