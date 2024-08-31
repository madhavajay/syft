"""
SyftBox Shared State: Where Global Variables Come to Party
==========================================================

Welcome to the shared state module, where thread-safety comes to die and global 
variables reign supreme! It's like a mosh pit for data, but with more locks and fewer 
crowd-surfers.

Step 1: Import the Bare Minimum
-------------------------------
We're only importing threading because we believe in the illusion of thread-safety:
"""

import threading  # For when we pretend to care about concurrency

"""
Step 2: Define the SharedState Class (aka "The Gossip Central")
---------------------------------------------------------------
This class is where all our plugins' secrets are stored and shared. It's like a 
high school locker room, but for data:
"""

class SharedState:
    def __init__(self):
        self.data = {}  # The vault of secrets
        self.lock = threading.Lock()  # Our bouncer, keeping the riff-raff out

    def get(self, key, namespace=None, default=None):
        """
        Gets a value from shared state. It's like gossip, but with better naming.
        """
        full_key = self._get_full_key(key, namespace)
        with self.lock:  # No peeking while we're fetching!
            return self.data.get(full_key, default)

    def set(self, key, value, namespace=None):
        """
        Sets a value in shared state. It's like writing on the bathroom wall, but more official.
        """
        full_key = self._get_full_key(key, namespace)
        with self.lock:  # Lock the stall door, we're writing something important
            self.data[full_key] = value

    def request_config(self, key, prompt_callback, namespace=None):
        """
        Requests a config value. It's like asking your mom for permission, but in code form.
        """
        full_key = self._get_full_key(key, namespace)
        with self.lock:  # Shh, the adults are talking
            if full_key not in self.data:
                # Time to phone a friend
                value = prompt_callback(key)
                self.data[full_key] = value
            return self.data[full_key]

    def _get_full_key(self, key, namespace):
        """
        Generates a full key. It's like a secret handshake, but less cool.
        """
        return f"{namespace}.{key}" if namespace else key

# Create a global instance of SharedState, because who doesn't love global variables?
shared_state = SharedState()

"""
Next Steps:
-----------
Congratulations! You've survived the shared state module. You're now ready for the 
grand finale. Proceed to plugins/plugin_hello.py to see where all this madness leads.
May your code be bug-free (but let's be real, it won't be).
"""
