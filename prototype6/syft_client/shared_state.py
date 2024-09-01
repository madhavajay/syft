from threading import Lock
import os

class SharedState:
    def __init__(self):
        self.data = {
            "syftbox_folder": os.path.expanduser("~/Desktop/SyftBox"),
            "syft_folder": os.path.expanduser("~/.syft")
        }
        self.lock = Lock()

    def get(self, key, default=None):
        with self.lock:
            if key == "my_datasites":
                return self._get_datasites()
            return self.data.get(key, default)

    def set(self, key, value):
        with self.lock:
            self.data[key] = value

    def _get_datasites(self):
        syft_folder = self.data.get("syft_folder")
        if not syft_folder or not os.path.exists(syft_folder):
            return []
        
        return [folder for folder in os.listdir(syft_folder) 
                if os.path.isdir(os.path.join(syft_folder, folder))]

shared_state = SharedState()