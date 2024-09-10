import logging
import os
from threading import Event

import requests

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = 5000  # Run every 5 seconds
DESCRIPTION = "A plugin that syncs new datasites to the cache server."

CACHE_SERVER_URL = "http://127.0.0.1:5000"  # Adjust this to your cache server's address
REQUEST_TIMEOUT = 10  # Timeout for requests in seconds

# Event to signal the plugin to stop
stop_event = Event()


def run(shared_state):
    if stop_event.is_set():
        logger.info("Plugin received stop signal before starting.")
        return

    try:
        sync_datasites(shared_state)
    except Exception as e:
        logger.error(f"Unexpected error in sync_new_datasites_to_cache: {str(e)}")


def get_all_users():
    url = f"{CACHE_SERVER_URL}/users"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to retrieve users from cache server: {str(e)}")
        return []


def add_user(username, public_key):
    url = f"{CACHE_SERVER_URL}/users"
    data = {"username": username, "public_key": public_key}
    try:
        response = requests.post(url, data=data, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            logger.info(f"User {username} added successfully!")
        elif response.status_code == 409:
            logger.warning(f"User {username} already exists.")
        else:
            logger.error(
                f"Failed to add user {username}. Status code: {response.status_code}"
            )
            logger.error(f"Response: {response.text}")
    except requests.RequestException as e:
        logger.error(f"An error occurred while adding user {username}: {str(e)}")


def sync_datasites(shared_state):
    syft_folder = shared_state.get("syft_folder")
    if not syft_folder:
        logger.warning("syft_folder is not set in shared state")
        return

    if not os.path.exists(syft_folder):
        logger.warning("syft_folder does not exist")
        return

    # Get all datasite folders in syft_folder
    local_datasites = [
        f
        for f in os.listdir(syft_folder)
        if os.path.isdir(os.path.join(syft_folder, f))
    ]

    # Get list of users from the cache server
    server_users = get_all_users()
    logger.info(f"Server users: {server_users}")

    # Find datasites that are not in the cache server
    new_datasites = set(local_datasites) - set(server_users)

    for datasite in new_datasites:
        try:
            # Read the public key
            public_key_path = os.path.join(syft_folder, datasite, "public_key.pem")
            if not os.path.exists(public_key_path):
                logger.warning(f"Public key not found for datasite: {datasite}")
                continue

            with open(public_key_path, "r") as key_file:
                public_key = key_file.read()

            # Register the new datasite with the cache server
            add_user(datasite, public_key)

        except Exception as e:
            logger.error(f"Error processing datasite {datasite}: {str(e)}")

    logger.info("Datasite synchronization with cache server completed")


def stop():
    stop_event.set()
    logger.info("Stop signal received for sync_new_datasites_to_cache plugin.")
