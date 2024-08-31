"""
Welcome to the Plugin Manager! It's like a daycare center for your plugins.

This file is responsible for loading, starting, stopping, and reloading plugins.
It also has a watchdog, which is like a babysitter that never sleeps.
"""

import importlib
import logging
import os
import sys
import threading
from typing import Dict, Any

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from shared_state import shared_state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PluginThread(threading.Thread):
    """
    This is our PluginThread. It's like a hamster wheel for your plugins to run in.
    """

    def __init__(self, plugin: Any, data: Dict[str, Any], shared_state: Any):
        """
        We're setting up the hamster wheel here. We give it a plugin (our hamster),
        some data (hamster food), and a shared state (the cage).
        """
        super().__init__()
        self.plugin = plugin
        self.data = data
        self.shared_state = shared_state
        self.stop_event = threading.Event()
        self.daemon = True

    def run(self) -> None:
        """
        This is where the magic happens. We let our plugin hamster run wild!
        If it falls off the wheel, we catch it (that's the try-except part).
        """
        try:
            self.plugin.execute(self.data, self.shared_state)
        except Exception as e:
            logger.error(f"Uh oh! Plugin {self.plugin.__name__} fell off the wheel: {e}")

    def stop(self) -> None:
        """
        This is like yelling "STOP!" at our hamster. It might listen, it might not.
        """
        self.stop_event.set()

class PluginManager:
    """
    The PluginManager is like a zookeeper for all our plugin animals.
    """

    def __init__(self, plugin_dir: str):
        """
        Setting up our zoo. We need a place for our animals (plugins) to live.
        """
        self.plugin_dir = plugin_dir
        self.plugins: Dict[str, Any] = {}
        self.plugin_threads: Dict[str, PluginThread] = {}
        self.lock = threading.Lock()
        self.observer: Observer = None

    def load_plugins(self) -> None:
        """Load all plugins from the plugin directory."""
        with self.lock:
            for filename in os.listdir(self.plugin_dir):
                if filename.endswith(".py"):
                    plugin_name = filename[:-3]
                    self.load_plugin(plugin_name)

    def load_plugin(self, plugin_name: str) -> None:
        """
        Load a specific plugin.

        Args:
            plugin_name: Name of the plugin to load.
        """
        try:
            module_name = f"plugins.{plugin_name}"
            module_path = os.path.join(self.plugin_dir, f"{plugin_name}.py")
            
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            if hasattr(module, 'execute'):
                self.plugins[plugin_name] = module
                logger.info(f"Loaded plugin: {plugin_name}")
            else:
                logger.warning(f"Plugin {plugin_name} has no execute function")
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}. Error: {e}")

    def start_plugin_thread(self, plugin_name: str) -> None:
        """
        Start a thread for a specific plugin.

        Args:
            plugin_name: Name of the plugin to start.
        """
        if plugin_name not in self.plugins:
            logger.warning(f"Plugin {plugin_name} not found")
            return
        
        plugin = self.plugins[plugin_name]
        thread = PluginThread(plugin, {'name': 'World'}, shared_state)
        thread.start()
        self.plugin_threads[plugin_name] = thread
        logger.info(f"Started thread for plugin: {plugin_name}")

    def stop_plugin_thread(self, plugin_name: str) -> None:
        """
        Stop a thread for a specific plugin.

        Args:
            plugin_name: Name of the plugin to stop.
        """
        if plugin_name in self.plugin_threads:
            thread = self.plugin_threads[plugin_name]
            thread.stop()
            thread.join(timeout=1)
            del self.plugin_threads[plugin_name]
            logger.info(f"Stopped thread for plugin: {plugin_name}")

    def reload_plugin(self, plugin_name: str) -> None:
        """
        Reload a specific plugin.

        Args:
            plugin_name: Name of the plugin to reload.
        """
        with self.lock:
            try:
                self.stop_plugin_thread(plugin_name)
                
                module_name = f"plugins.{plugin_name}"
                if module_name in sys.modules:
                    del sys.modules[module_name]
                if plugin_name in self.plugins:
                    del self.plugins[plugin_name]
                
                self.load_plugin(plugin_name)
                logger.info(f"Successfully reloaded plugin: {plugin_name}")
            except Exception as e:
                logger.error(f"Failed to reload plugin {plugin_name}. Error: {e}")

    def start_watchdog(self) -> None:
        """Start the watchdog for hot-reloading plugins."""
        event_handler = PluginReloader(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.plugin_dir, recursive=False)
        self.observer.start()

    def stop_watchdog(self) -> None:
        """Stop the watchdog."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=1)

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_watchdog()
        for plugin_name in list(self.plugin_threads.keys()):
            self.stop_plugin_thread(plugin_name)


class PluginReloader(FileSystemEventHandler):
    """
    This is our PluginReloader. It's like a really eager kid watching for changes
    in the plugin playground.
    """

    def __init__(self, plugin_manager: PluginManager):
        """
        We give our eager kid a walkie-talkie connected to the PluginManager.
        """
        self.plugin_manager = plugin_manager

    def on_modified(self, event):
        """
        When a file changes, our eager kid yells "CHANGE!" into the walkie-talkie.
        """
        if event.src_path.endswith(".py"):
            plugin_name = os.path.basename(event.src_path)[:-3]
            logger.info(f"Hot reloading {event.src_path}")
            self.plugin_manager.reload_plugin(plugin_name)
