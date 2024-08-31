"""
SyftBox Shared State: Where Global Variables Come to Party
==========================================================

Welcome to the shared state module, where thread-safety comes to die and global 
variables reign supreme! It's like a mosh pit for data, but with more locks and fewer 
crowd-surfers.

Step 1: Import the Bare Minimum
-------------------------------
We're importing threading for our illusion of thread-safety, and typing for our type checks:
"""

import threading
from typing import Dict, Any, Optional, Callable

"""
Step 2: Define the SharedState Class (aka "The Gossip Central")
---------------------------------------------------------------
This class is where all our plugins' secrets are stored and shared. It's like a 
high school locker room, but for data:
"""

class SharedState:
    def __init__(self):
        self.data: Dict[str, Any] = {}  # The vault of secrets
        self.lock: threading.Lock = threading.Lock()  # Our bouncer, keeping the riff-raff out

    def get(self, key: str, namespace: Optional[str] = None, default: Any = None) -> Any:
        """
        Gets a value from shared state. It's like gossip, but with better naming.
        """
        full_key: str = self._get_full_key(key, namespace)
        with self.lock:  # No peeking while we're fetching!
            return self.data.get(full_key, default)

    def set(self, key: str, value: Any, namespace: Optional[str] = None) -> None:
        """
        Sets a value in shared state. It's like writing on the bathroom wall, but more official.
        """
        full_key: str = self._get_full_key(key, namespace)
        with self.lock:  # Lock the stall door, we're writing something important
            self.data[full_key] = value

    def request_config(self, key: str, prompt_callback: Callable[[str], Any], namespace: Optional[str] = None) -> Any:
        """
        Requests a config value. It's like asking your mom for permission, but in code form.
        """
        full_key: str = self._get_full_key(key, namespace)
        with self.lock:  # Shh, the adults are talking
            if full_key not in self.data:
                # Time to phone a friend
                value: Any = prompt_callback(key)
                self.data[full_key] = value
            return self.data[full_key]

    def _get_full_key(self, key: str, namespace: Optional[str]) -> str:
        """
        Generates a full key. It's like a secret handshake, but less cool.
        """
        return f"{namespace}.{key}" if namespace else key

# Create a global instance of SharedState, because who doesn't love global variables?
shared_state: SharedState = SharedState()

"""
Next Steps:
-----------
Congratulations! You've survived the shared state module. You're now ready for the 
grand finale. Proceed to plugins/plugin_hello.py to see where all this madness leads.
May your code be bug-free (but let's be real, it won't be).
"""
