"""
Welcome to the SyftBox Accounts Plugin: The Magical Datasite Registry! 🧙‍♂️📚

This plugin manages datasite accounts, including creating and storing keypairs,
and ensuring that public keys are properly distributed to the SyftBox folder.
"""

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict


logger = logging.getLogger(__name__)


def prompt_callback(key: str) -> str:
    """
    Prompts the user for the syft folder location and handles different responses.
    """
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            folder_path = input(
                f"Where do you want your syft folder? "
                f"(Hit Enter for ~/.syft) Attempt {attempt + 1}/{max_attempts}: "
            ).strip()
            if not folder_path:
                logger.info("Using default ~/.syft folder.")
                return os.path.expanduser("~/.syft")
            elif folder_path.startswith("~/"):
                folder_path = os.path.expanduser(folder_path)

            if os.path.isdir(folder_path):
                return folder_path
            else:
                try:
                    os.makedirs(folder_path, exist_ok=True)
                    logger.info(f"Created new directory: {folder_path}")
                    return folder_path
                except OSError as e:
                    logger.warning(
                        f"Failed to create directory '{folder_path}'. Error: {e}"
                    )
                    logger.warning("Try again with a different path.")
        except EOFError:
            logger.warning("Input interrupted. Using default ~/.syft folder.")
            return os.path.expanduser("~/.syft")

    logger.warning("Max attempts reached. Using default ~/.syft folder.")
    return os.path.expanduser("~/.syft")


def get_user_input(data: Dict[str, Any], shared_state: Any) -> None:
    """
    Gets user input for the syft folder location and stores it in shared state.
    """
    # First, prompt the user for their preferred syft folder
    syft_folder = prompt_callback("syft_folder")

    # Store the user's choice in shared state
    shared_state.set("syft_folder", syft_folder, namespace="init_my_datasites")

    print(f"Syft folder set to: {syft_folder}")

    # Now prompt for datasite names
    while True:
        new_datasite = input(
            "Enter a datasite name (or press Enter to finish): "
        ).strip()
        if not new_datasite:
            break

        datasite_folder = Path(syft_folder) / new_datasite
        if not datasite_folder.exists():
            datasite_folder.mkdir(parents=True, exist_ok=True)
            print(f"Created folder for datasite: {new_datasite}")
        else:
            print(f"Folder for datasite {new_datasite} already exists.")


def execute(data: Dict[str, Any], shared_state: Any) -> None:
    """
    Ensures that each datasite has a folder in the SyftBox directory and that
    the public key is copied to that folder.
    """
    while True:
        try:
            syft_folder = Path(
                shared_state.get("syft_folder", namespace="init_my_datasites")
            )
            syftbox_folder = shared_state.get(
                "syftbox_folder", namespace="hello_plugin"
            )

            if not syftbox_folder:
                print("SyftBox folder not set. Please run the setup wizard first.")
                return

            syftbox_path = Path(syftbox_folder)

            if not syftbox_path.exists():
                print(
                    f"SyftBox folder does not exist at {syftbox_path}. Please run the setup wizard first."
                )
                return

            # Get datasite names from existing folders in .syft
            datasite_names = [
                folder.name for folder in syft_folder.iterdir() if folder.is_dir()
            ]

            for datasite in datasite_names:
                datasite_folder = syftbox_path / datasite
                datasite_folder.mkdir(exist_ok=True)

                source_public_key = syft_folder / datasite / "public_key.pem"
                destination_public_key = datasite_folder / "public_key.pem"

                if not destination_public_key.exists():
                    if source_public_key.exists():
                        shutil.copy(source_public_key, destination_public_key)
                        print(f"Copied public key for {datasite} to {datasite_folder}")
                    else:
                        print(
                            f"Public key for {datasite} not found in {syft_folder / datasite}"
                        )
                else:
                    logging.debug(
                        f"Public key for {datasite} already exists in {datasite_folder}"
                    )

                # Create or update the .syftperm file
                syftperm_file = destination_public_key.with_suffix(".pem.syftperm")

                if not syftperm_file.exists():
                    syftperm_content = {"READ": ["EVERYONE", datasite]}

                    with open(syftperm_file, "w") as f:
                        json.dump(syftperm_content, f, indent=2)

                    print(f"Created/updated .syftperm file for {datasite}")

        except Exception as e:
            logging.error(
                f"Error in execute function for pluging 'init_my_datasites': {e}"
            )

        time.sleep(1)

    print(
        "Finished setting up datasite folders and copying public keys in the SyftBox folder."
    )


"""
Congratulations! You've set up the Accounts plugin for SyftBox. 🎉

This plugin manages datasite accounts, generates keypairs, and ensures that
public keys are properly distributed to the SyftBox folder.

Next, you might want to create plugins that use these datasite accounts
for various operations within SyftBox!
"""
