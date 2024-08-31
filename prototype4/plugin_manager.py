import importlib
import os
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import logging
import rumps

class PluginReloader(FileSystemEventHandler):
    def __init__(self, plugin_manager):
        self.plugin_manager = plugin_manager

    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            logging.info(f"Detected change in {event.src_path}. Reloading plugin...")
            self.plugin_manager.reload_plugin(os.path.basename(event.src_path))

class PluginManager:
    def __init__(self, plugin_dir, shared_state):
        self.plugin_dir = plugin_dir
        self.shared_state = shared_state
        self.plugins = {}
        self.lock = threading.Lock()

    def load_plugins(self):
        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py"):
                plugin_name = filename[:-3]
                self.load_plugin(plugin_name)

    def load_plugin(self, plugin_name):
        try:
            module = importlib.import_module(f"plugins.{plugin_name}")
            if hasattr(module, 'execute'):
                with self.lock:
                    self.plugins[plugin_name] = module.execute({}, self.shared_state)
                logging.info(f"Loaded plugin: {plugin_name}")
            else:
                logging.error(f"Plugin {plugin_name} does not have an execute function")
        except Exception as e:
            logging.error(f"Failed to load plugin {plugin_name}: {e}")

    def reload_plugin(self, plugin_name):
        module_name = f"plugins.{plugin_name[:-3]}"
        with self.lock:
            if module_name in sys.modules:
                try:
                    module = importlib.reload(sys.modules[module_name])
                    if hasattr(module, 'execute'):
                        self.plugins[plugin_name[:-3]] = module.execute({}, self.shared_state)
                        logging.info(f"Reloaded plugin: {plugin_name[:-3]}")
                    else:
                        logging.error(f"Reloaded plugin {plugin_name[:-3]} does not have an execute function")
                except Exception as e:
                    logging.error(f"Failed to reload plugin {plugin_name[:-3]}: {e}")

    def execute_plugins(self):
        with self.lock:
            for plugin_name, plugin_func in self.plugins.items():
                try:
                    plugin_func()
                except Exception as e:
                    logging.error(f"Error executing plugin {plugin_name}: {e}")

    def run_plugins(self, stop_event):
        while not stop_event.is_set():
            self.execute_plugins()
            stop_event.wait(5)  # Run every 5 seconds

    def start_watchdog(self):
        event_handler = PluginReloader(self)
        observer = Observer()
        observer.schedule(event_handler, self.plugin_dir, recursive=False)
        observer.start()
        return observer