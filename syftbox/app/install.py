import argparse
import json
import os
import re
import shutil
import subprocess
import platform
from types import SimpleNamespace
from typing import Tuple
from .utils import get_config_path
from ..lib import ClientConfig

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
        raise Exception(
            "git cli isn't installed. Please, follow the instructions"
            + " to install git according to your OS. (eg. brew install git)"
        )

    # Clone repository in /tmp
    repo_url = f"https://github.com/{sanitized_git_path}.git"
    temp_clone_path = f"{TEMP_PATH}/{sanitized_git_path.split('/')[-1]}"

    # Delete if there's already an existent repository folder in /tmp path.
    delete_folder_if_exists(temp_clone_path)

    try:
        subprocess.run(
            ["git", "clone", repo_url, temp_clone_path],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
    if os.path.islink(target_symlink_path):
        os.unlink(target_symlink_path)
    os.symlink(app_path, target_symlink_path)


def load_config(path: str):
    with open(path, "r") as f:
        data = json.load(f)
    return dict_to_namespace(data)


def move_repository_to_syftbox(tmp_clone_path: str, sanitized_path: str):
    output_path = f"{get_config_path()}/apps/{sanitized_path.split('/')[-1]}"
    # Check and delete if there's already the same repository
    # name in ~/.syftbox/apps directory.
    delete_folder_if_exists(output_path)
    shutil.move(tmp_clone_path, output_path)
    return output_path


def run_pre_install(config):
    if len(getattr(config.app, "pre_install", [])) == 0:
        return

    subprocess.run(
        config.app.pre_install,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_post_install(config):
    if len(getattr(config.app, "post_install", [])) == 0:
        return

    subprocess.run(
        config.app.post_install,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def check_os_compatibility(app_config):
    os_name = platform.system().lower()
    supported_os = getattr(app_config.app, "platforms", [])

    # If there's no platforms field in config.json, just ignore it.
    if len(supported_os) == 0:
        return

    is_compatible = False
    for operational_system in supported_os:
        if operational_system.lower() == os_name:
            is_compatible = True

    if not is_compatible:
        raise Exception("Your OS isn't supported by this app.")


def get_current_commit(app_path):
    try:
        # Navigate to the repository path and get the current commit hash
        commit_hash = (
            subprocess.check_output(
                ["git", "-C", app_path, "rev-parse", "HEAD"], stderr=subprocess.STDOUT
            )
            .strip()
            .decode("utf-8")
        )
        return commit_hash
    except subprocess.CalledProcessError as e:
        return f"Error: {e.output.decode('utf-8')}"


def update_app_config_file(app_path: str, sanitized_git_path: str, app_config) -> None:
    normalized_app_path = os.path.normpath(app_path)

    conf_path = os.path.dirname(os.path.dirname(normalized_app_path))

    app_json_path = conf_path + "/app.json"
    app_json_config = {}
    if os.path.exists(app_json_path):
        # Read from it.
        app_json_config = vars(load_config(app_json_path))

    app_version = None
    if getattr(app_config.app, "version", None) is not None:
        app_version = app_config.app.version

    app_json_config[sanitized_git_path] = {
        "commit": get_current_commit(normalized_app_path),
        "version": app_version,
    }

    with open(app_json_path, "w") as json_file:
        json.dump(app_json_config, json_file, indent=4)


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
        # Check OS platform compatibility
        # Handles if app isn't compatible with the target os system.
        step = "Checking platform compatibility."
        check_os_compatibility(app_config)

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
        update_app_config_file(app_path, sanitized_path, app_config)
    except Exception as e:
        return (step, e)
