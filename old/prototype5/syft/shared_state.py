"""
Welcome to the SyftBox Shared State: The Playground's Bulletin Board! 📌✨

Toy Box Story:
Imagine you have a magical bulletin board in your playground. All the toys can write messages,
draw pictures, or stick notes on this board. When a toy wants to share something with other toys,
it puts it on the board. When a toy wants to know what others have shared, it looks at the board.
But here's the catch - only one toy can write or read from the board at a time, so they don't
accidentally erase each other's messages!

Reality:
In the world of software, this magical bulletin board is what we call "shared state". It's a way
for different parts of a program (in our case, plugins) to share information with each other.
The SharedState class acts like our bulletin board, allowing plugins to store and retrieve data.
We use something called a "lock" to make sure only one plugin can change or read the shared data
at a time, keeping everything neat and tidy.

Let's dive into the world of shared secrets and see how our magical bulletin board works! 🚀
"""

import threading
from typing import Any, Callable, Dict, Optional

"""
Step 1: The Magical Bulletin Board 📋 (SharedState Class)

Toy analogy: This is our special bulletin board where toys can share their secrets and stories.

Reality: We create a class called SharedState that will manage our shared data and ensure
thread-safe access to it.
"""


class SharedState:
    def __init__(self):
        """
        Step 1a: Setting Up the Bulletin Board

        Toy analogy: We're putting up our bulletin board and getting our special marker ready.

        Reality: We're initializing our shared data dictionary and creating a lock for thread-safety.
        """
        self.data: Dict[str, Any] = {}  # Our magical bulletin board
        self.lock: threading.Lock = (
            threading.Lock()
        )  # Our special marker that only one toy can use at a time

    def get(
        self, key: str, namespace: Optional[str] = None, default: Any = None
    ) -> Any:
        """
        Step 1b: Reading from the Bulletin Board 👀

        Toy analogy: A toy wants to read a message from the board.

        Reality: This method retrieves a value from the shared state, using a namespace if provided.
        """
        full_key: str = self._get_full_key(key, namespace)
        with self.lock:  # Only one toy can read at a time
            return self.data.get(full_key, default)

    def set(self, key: str, value: Any, namespace: Optional[str] = None) -> None:
        """
        Step 1c: Writing on the Bulletin Board ✍️

        Toy analogy: A toy wants to stick a new note on the board.

        Reality: This method sets a value in the shared state, using a namespace if provided.
        """
        full_key: str = self._get_full_key(key, namespace)
        with self.lock:  # Only one toy can write at a time
            self.data[full_key] = value

    def request_config(
        self,
        key: str,
        prompt_callback: Callable[[str], Any],
        namespace: Optional[str] = None,
    ) -> Any:
        """
        Step 1d: Asking for Help 🙋

        Toy analogy: If a toy can't find a message on the board, it asks a grown-up for help.

        Reality: This method tries to get a config value, and if it doesn't exist, it uses a callback to prompt for it.
        """
        full_key: str = self._get_full_key(key, namespace)
        with self.lock:  # We don't want other toys interrupting while we're asking for help
            if full_key not in self.data:
                # Time to ask a grown-up (use the callback)
                value: Any = prompt_callback(key)
                self.data[full_key] = value
            return self.data[full_key]

    def _get_full_key(self, key: str, namespace: Optional[str]) -> str:
        """
        Step 1e: Finding the Right Spot on the Board 🔍

        Toy analogy: We have different sections on our board for different types of messages.

        Reality: This method generates a full key using the namespace (if provided) and the key.
        """
        return f"{namespace}.{key}" if namespace else key


# Step 2: Making Our Bulletin Board Available to Everyone 🌍
# ---------------------------------------------------------
# We create a global instance of SharedState so all our plugins can use the same bulletin board.
shared_state: SharedState = SharedState()

"""
Congratulations, you've mastered the art of sharing secrets! 🎉🧙‍♂️

You've learned how our magical bulletin board (SharedState) works, allowing toys (plugins)
to share information and work together in harmony.

What's next on your adventure, you ask?

Head over to syft/plugins/plugin_setup/plugin.py to see how our plugins use this shared state
to communicate and do amazing things!

Remember, in the world of coding, sharing is caring (but always do it safely)! Happy exploring!
"""
