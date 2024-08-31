"""
Welcome to the SyftBox Configuration Plugin!

This plugin is like a helpful robot that sets up your SyftBox folder.
It asks you where you want your folder, and if you don't answer, it just puts
it on your desktop. Because robots know best, right?

"""

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


def prompt_callback(key: str) -> str:
    """
    This is our robot's voice. It asks you where you want your SyftBox folder.
    If you ignore it three times, it gets annoyed and puts the folder on your desktop.
    """
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            folder_path = input(
                f"Hey you! Where do you want your SyftBox Folder? "
                f"(Hit Enter for Desktop/SyftBox) Attempt {attempt + 1}/{max_attempts}: "
            ).strip()
            if not folder_path:
                logger.warning("You said nothing. Desktop it is!")
                return os.path.expanduser("~/Desktop/SyftBox")

            if os.path.isdir(folder_path):
                return folder_path
            else:
                print(
                    f"Um, '{folder_path}' isn't a real place. Try again, smartypants."
                )
        except EOFError:
            logger.warning("You broke the input. Desktop for you!")
            return os.path.expanduser("~/Desktop/SyftBox")

    logger.warning("Three strikes, you're out! Desktop it is!")
    return os.path.expanduser("~/Desktop/SyftBox")


def execute(data: Dict[str, Any], shared_state: Any) -> str:
    """
    This is where our robot does its job. It asks where to put the folder,
    then it makes the folder. If it can't make the folder, it throws a tantrum (raises an error).
    """
    try:
        folder = shared_state.request_config(
            "syftbox_folder", prompt_callback, namespace="hello_plugin"
        )

        print(f"Ta-da! Your SyftBox Folder is at: {folder}")

        os.makedirs(folder, exist_ok=True)

        logger.info(f"Look at me, I made a folder at {folder}!")
        return folder
    except OSError as e:
        error_message = f"Failed to set SyftBox Folder. Error: {e}"
        logger.error(error_message)
        raise
