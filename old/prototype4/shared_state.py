import threading
import json
from typing import Any, Callable, Optional

class SharedState:
    def __init__(self):
        self.data: dict = {}
        self.lock = threading.Lock()

    def get(self, key: str, namespace: Optional[str] = None, default: Any = None) -> Any:
        full_key = self._get_full_key(key, namespace)
        with self.lock:
            return self.data.get(full_key, default)

    def set(self, key: str, value: Any, namespace: Optional[str] = None) -> None:
        full_key = self._get_full_key(key, namespace)
        with self.lock:
            self.data[full_key] = value

    def request_config(self, key: str, prompt_callback: Callable[[str], Any], namespace: Optional[str] = None) -> Any:
        full_key = self._get_full_key(key, namespace)
        with self.lock:
            if full_key not in self.data:
                value = prompt_callback(key)
                self.data[full_key] = value
            return self.data[full_key]

    def _get_full_key(self, key: str, namespace: Optional[str]) -> str:
        return f"{namespace}.{key}" if namespace else key

    def save_to_file(self, filename: str) -> None:
        with self.lock:
            with open(filename, 'w') as f:
                json.dump(self.data, f)

    def load_from_file(self, filename: str) -> None:
        with self.lock:
            with open(filename, 'r') as f:
                self.data = json.load(f)

shared_state = SharedState()