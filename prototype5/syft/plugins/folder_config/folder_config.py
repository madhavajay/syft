"""
Welcome to the SyftBox Configuration Plugin: The Toy Box Setup Wizard! 🧙‍♂️📦

Toy Box Story:
Imagine you're a magical toy that helps set up the perfect playroom for all the other toys.
Your job is to ask the toy owner where they want to put the special toy box. If they don't
answer, you use your magic to put it on their desk. Because magical toys know best, right?

Reality:
In the world of software, this plugin is responsible for setting up the SyftBox folder.
It interacts with the user to determine where to place the folder, and if the user doesn't
specify a location, it defaults to creating the folder on the desktop.

Let's dive into the magical world of folder creation and see how our setup wizard works! 🚀
"""

import logging
import os
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

"""
Step 1: The Magical Voice 🗣️ (User Interaction)

Toy analogy: This is like the magical voice that asks the toy owner where to put the toy box.

Reality: We create a function that prompts the user for input and handles various scenarios.
"""


def prompt_callback(key: str) -> str:
    """
    Step 1a: Asking the Big Question

    Toy analogy: We're using our magical voice to ask where to put the toy box.

    Reality: This function prompts the user for the SyftBox folder location and handles different responses.
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
            logger.warning("You broke the input. Desktop for you!")
            return os.path.expanduser("~/Desktop/SyftBox")

    logger.warning("Three strikes, you're out! Desktop it is!")
    return os.path.expanduser("~/Desktop/SyftBox")


"""
Step 2: The Toy Box Creator 🛠️ (Main Plugin Function)

Toy analogy: This is the magical spell that actually creates the toy box in the right place.

Reality: We define the main function that sets up the SyftBox folder using the shared state.
"""


def get_user_input(data: Dict[str, Any], shared_state: Any) -> None:
    _ = shared_state.request_config(
        "syftbox_folder", prompt_callback, namespace="hello_plugin"
    )


def execute(data: Dict[str, Any], shared_state: Any) -> str:
    """
    Step 2a: Casting the Spell

    Toy analogy: We're using our magic to create the perfect toy box in the chosen spot.

    Reality: This function uses the shared state to get or set the SyftBox folder location,
    creates the folder, and returns its path.
    """
    try:
        while True:
            folder = shared_state.request_config(
                "syftbox_folder", prompt_callback, namespace="hello_plugin"
            )

            logger.debug(f"Ta-da! Your SyftBox Folder is at: {folder}")

            os.makedirs(folder, exist_ok=True)

            logger.debug(f"Look at me, I made a folder at {folder}!")

            time.sleep(2)
    except OSError as e:
        error_message = f"Failed to set SyftBox Folder. Error: {e}"
        logger.error(error_message)
        raise


"""
Congratulations, you've mastered the art of magical folder creation! 🎉🧙‍♂️

You've learned how our setup wizard (plugin) interacts with the user and the shared state
to create the perfect home for all the other plugins.

What's next on your adventure, you ask?

Head back to syft/main.py to see how all these magical components work together in the
grand circus of SyftBox!

Remember, in the world of coding, even folder creation can be a magical adventure! Happy exploring!
"""
