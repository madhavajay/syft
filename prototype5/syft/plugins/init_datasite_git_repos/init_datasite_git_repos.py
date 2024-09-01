"""
SyftBox Git Repository Initializer Plugin

This plugin initializes git repositories in each datasite folder within the SyftBox directory
if they don't already exist.
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def get_user_input(data: Dict[str, Any], shared_state: Any) -> None:
    """This plugin doesn't require user input."""
    pass


def execute(data: Dict[str, Any], shared_state: Any) -> None:
    """
    Iterates through all datasite folders in the SyftBox directory and initializes
    a git repository in each folder if one doesn't already exist.
    """
    while True:
        try:
            syftbox_folder = shared_state.get(
                "syftbox_folder", namespace="hello_plugin"
            )

            if not syftbox_folder:
                logger.error(
                    "SyftBox folder not set. Please run the setup wizard first."
                )
                time.sleep(5)
                continue

            syftbox_path = Path(syftbox_folder)

            if not syftbox_path.exists():
                logger.error(
                    f"SyftBox folder does not exist at {syftbox_path}. Please run the setup wizard first."
                )
                time.sleep(5)
                continue

            for datasite_folder in syftbox_path.iterdir():
                if datasite_folder.is_dir():
                    git_dir = datasite_folder / ".git"
                    if not git_dir.exists():
                        try:
                            subprocess.run(
                                ["git", "init"],
                                cwd=str(datasite_folder),
                                check=True,
                                capture_output=True,
                            )
                            logger.info(
                                f"Initialized git repository in {datasite_folder}"
                            )
                        except subprocess.CalledProcessError as e:
                            logger.error(
                                f"Failed to initialize git repository in {datasite_folder}. Error: {e}"
                            )
                    else:
                        logger.debug(
                            f"Git repository already exists in {datasite_folder}"
                        )

            logger.info("Finished checking and initializing git repositories.")
        except Exception as e:
            logger.error(
                f"Error in execute function for plugin 'init_datasite_git_repos': {e}"
            )

        time.sleep(5)  # Wait for 5 seconds before the next iteration


"""
This plugin ensures that each datasite folder within the SyftBox directory has a git repository.
It runs continuously, checking for new folders and initializing git repositories as needed.
"""
