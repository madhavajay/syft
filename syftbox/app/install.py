import argparse
import json
import os
import re
import shutil
import subprocess
from os.path import islink
from sys import exception
from types import SimpleNamespace
from typing import Tuple

from ..lib import ClientConfig
from .utils import base_path

TEMP_PATH = "/tmp/apps/"


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


def sanitize_git_path(path):
    # Define a regex pattern for a valid GitHub path
    pattern = r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$"

    # Check if the path matches the pattern
    if re.match(pattern, path):
        return path
    else:
        raise ValueError("Invalid Git repository path format.")


def delete_folder_if_exists(folder_path: str):
    # Check if temp clone path already exists, if so, delete it.
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        shutil.rmtree(folder_path)


def clone_repository(sanitized_git_path: str) -> str:
    if not is_git_installed():
        raise Exception("Git isn't installed.")

    # Clone repository in /tmp
    repo_url = f"https://github.com/{sanitized_git_path}.git"
    temp_clone_path = f"{TEMP_PATH}/{sanitized_git_path.split('/')[-1]}"

    # Delete if there's already an existent repository folder in /tmp path.
    delete_folder_if_exists(temp_clone_path)

    try:
        subprocess.run(
            ["git", "clone", repo_url, temp_clone_path], check=True, text=True
        )
        return temp_clone_path
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e}")
        raise e


def dict_to_namespace(data):
    if isinstance(data, dict):
        return SimpleNamespace(
            **{key: dict_to_namespace(value) for key, value in data.items()}
        )
    elif isinstance(data, list):
        return [dict_to_namespace(item) for item in data]
    else:
        return data


def set_environment_values(config, app_path: str):
    env_namespace = getattr(config.app, "env", None)
    if env_namespace is None:
        return

    env_vars = vars(env_namespace)

    with open(f"{app_path}/.env", "w") as envfile:
        for key, val in env_vars.items():
            envfile.write(f"export {key}={val}\n")
    try:
        subprocess.run(["source", f"{app_path}/.env"], check=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e}")
        raise e


def create_symbolic_link(
    client_config: ClientConfig, app_path: str, sanitized_path: str
):
    # TODO: Create a Symlink function
    # - Handles if symlink already exists
    # - Handles if path doesn't exists.
    target_symlink_path = (
        f"{str(client_config.sync_folder)}/apps/{sanitized_path.split('/')[-1]}"
    )

    # Create the symlink
    try:
        if os.path.islink(target_symlink_path):
            os.unlink(target_symlink_path)
        os.symlink(app_path, target_symlink_path)
        print(f"Symlink created: {target_symlink_path} -> {app_path}")
    except FileExistsError:
        print(f"Symlink already exists: {target_symlink_path}")


def load_config(path: str):
    with open(path, "r") as f:
        data = json.load(f)
    return dict_to_namespace(data)


def move_repository_to_syftbox(tmp_clone_path: str, sanitized_path: str):
    output_path = f"{base_path}/apps/{sanitized_path.split('/')[-1]}"
    # Check and delete if there's already the same repository
    # name in ~/.syftbox/apps directory.
    delete_folder_if_exists(output_path)
    shutil.move(tmp_clone_path, output_path)
    return output_path


def run_pre_install(config):
    if len(getattr(config.app, "pre_install", [])) == 0:
        return

    try:
        subprocess.run(config.app.pre_install, check=True, text=True)
    except subprocess.CalledProcessError:
        return False


def run_post_install(config):
    if len(getattr(config.app, "post_install", [])) == 0:
        return

    try:
        subprocess.run(config.app.post_install, check=True, text=True)
    except subprocess.CalledProcessError:
        return False


def update_app_config_file():
    pass


def install(client_config: ClientConfig) -> None | Tuple[str, Exception]:
    parser = argparse.ArgumentParser(description="Run FastAPI server")

    parser.add_argument("repository", type=str, help="App repository")

    args = parser.parse_args()
    step = ""
    try:
        # NOTE:
        # Sanitize git repository path
        # Handles: bad format repository path.
        # Returns: Sanitized repository path.
        step = "Checking app name"
        sanitized_path = sanitize_git_path(args.repository)

        # NOTE:
        # Clones the app repository
        # Handles: Git cli tool not installed.
        # Handles: Repository path doesn't exits / isn't public.
        # Handles: If /tmp/apps/<repository_name> already exists (replaces it)
        # Returns: Path where the repository folder was cloned temporarily.
        step = "Pulling App"
        tmp_clone_path = clone_repository(sanitized_path)

        # NOTE:
        # Load config.json
        # Handles: config.json doesn't exist in the pulled repository
        # Handles: config.json version is different from syftbox config version.
        # Returns: Loaded app config as SimpleNamespace instance.
        step = "Loading config.json"
        app_config = load_config(tmp_clone_path + "/config.json")

        # NOTE:
        # Moves the repository from /tmp to ~/.syftbox/apps/<repository_name>
        # Handles: If ~/.syftbox/apps/<repository_name> already exists (replaces it)
        app_path = move_repository_to_syftbox(
            tmp_clone_path=tmp_clone_path, sanitized_path=sanitized_path
        )

        # NOTE:
        # Creates a Symbolic Link ( ~/Desktop/Syftbox/app/<rep> -> ~/.syftbox/apps/<rep>)
        # Handles: If ~/.syftbox/apps/<repository_name> already exists (replaces it)
        step = "Creating Symbolic Link"
        create_symbolic_link(
            client_config=client_config,
            app_path=app_path,
            sanitized_path=sanitized_path,
        )

        # NOTE:
        # Set app environment variables.
        # set_environment_values(app_config, app_path)

        # NOTE:
        # Executes config.json pre-install command list
        # Handles: Exceptions from pre-install command execution
        step = "Running pre-install commands"
        run_pre_install(app_config)

        # NOTE:
        # Executes config.json post-install command list
        # Handles: Exceptions from post-install command execution
        step = "Running post-install commands"
        run_post_install(app_config)

        # NOTE:
        # Updates the apps.json file
        # Handles: If apps.json file doesn't exist yet.
        # Handles: If apps.json already have the repository_name  app listed.
        # Handles: If apps.json exists but doesn't have the repository_name app listed.
        step = "Updating apps.json config"
        update_app_config_file()
    except Exception as e:
        return (step, e)
