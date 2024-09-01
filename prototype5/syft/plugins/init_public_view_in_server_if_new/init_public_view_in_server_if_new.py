"""
SyftBox My Datasites Plugin

This plugin prints the names of all datasites that have a corresponding private key
in the ~/.syft folder every 2 seconds.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def get_user_input(data: Dict[str, Any], shared_state: Any) -> None:
    """This plugin doesn't require user input."""
    pass


def execute(data: Dict[str, Any], shared_state: Any) -> None:
    """
    Prints the names of all datasites with a corresponding private key in ~/.syft
    every 2 seconds.
    """
    while True:
        try:
            syft_folder = Path.home() / ".syft"

            # Get datasite names from existing folders in .syft that have private keys
            datasite_names = [
                folder.name
                for folder in syft_folder.iterdir()
                if folder.is_dir() and (folder / "private_key.pem").exists()
            ]

            if datasite_names:
                print("My datasites:")
                for datasite in datasite_names:
                    print(f"- {datasite}")
            else:
                print("No datasites found with private keys.")

        except Exception as e:
            logger.error(
                f"Error in execute function for plugin 'init_my_datasites': {e}"
            )

        time.sleep(2)  # Wait for 2 seconds before the next iteration


"""
This plugin continuously prints the names of datasites that have a private key
in the ~/.syft folder every 2 seconds.
"""
