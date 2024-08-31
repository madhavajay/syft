import logging
import os
import time
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)


def get_user_input(data: Dict[str, Any], shared_state: Any) -> None:
    """nothing"""


def execute(data: Dict[str, Any], shared_state: Any) -> None:
    """
    Execute function for the Hello World plugin.
    This function will synchronize folders in the SyftBox directory with users on the server,
    creating folders for users that don't have them and adding users for folders that don't have them.
    """
    syftbox_dir = shared_state.get("syftbox_folder", namespace="hello_plugin")

    if not syftbox_dir or not os.path.isdir(syftbox_dir):
        logger.error(f"SyftBox directory not found or invalid: {syftbox_dir}")
        return

    server_url = "http://localhost:8082/users"

    while True:
        folders = set(
            f
            for f in os.listdir(syftbox_dir)
            if os.path.isdir(os.path.join(syftbox_dir, f))
        )

        try:
            response = requests.get(server_url)
            if response.status_code == 200:
                server_users = set(response.json())

                # Add users for folders that don't have them
                for folder in folders - server_users:
                    logger.warning(
                        f"Folder '{folder}' does not have a corresponding user in the server. Adding user..."
                    )
                    add_response = requests.post(server_url, json={"username": folder})
                    if add_response.status_code == 201:
                        logger.info(
                            f"User '{folder}' added successfully to the server."
                        )
                    else:
                        logger.error(
                            f"Failed to add user '{folder}' to the server. Status code: {add_response.status_code}"
                        )

                # Create folders for users that don't have them
                for user in server_users - folders:
                    logger.warning(
                        f"User '{user}' does not have a corresponding folder. Creating folder..."
                    )
                    try:
                        os.mkdir(os.path.join(syftbox_dir, user))
                        logger.info(
                            f"Folder '{user}' created successfully in the SyftBox directory."
                        )
                    except OSError as e:
                        logger.error(
                            f"Failed to create folder '{user}' in the SyftBox directory. Error: {e}"
                        )

                logger.debug(f"Folders in SyftBox directory: {', '.join(folders)}")
                logger.debug(f"Users on the server: {', '.join(server_users)}")
            else:
                logger.error(
                    f"Failed to retrieve users from server. Status code: {response.status_code}"
                )

        except requests.RequestException as e:
            logger.error(f"Error connecting to the server: {e}")

        time.sleep(1)


# This plugin doesn't need to return anything, so we don't include a return statement.
