"""
Welcome to the Magical Plugin Playground! 🎪✨

Imagine you have a toy box full of different toys (we call them plugins).
This playground helps you manage and run all your plugins efficiently.
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

"""
Step 1: The Toy Runner 🏃‍♂️ (Thread Creation)

Toy analogy: This is like a special track where each toy can run and play.

Reality: We create a separate thread for each plugin to run independently.
This allows multiple plugins to operate concurrently without interfering with each other.
"""
class PluginThread(threading.Thread):
    
    def __init__(self, plugin: Any, data: Dict[str, Any], shared_state: Any):
        """
        Step 1a: Setting Up the Track

        Toy analogy: We're setting up the track for our toy to run on.

        Reality: We're initializing the thread with the plugin, its data, and shared state.
        """
        super().__init__()
        self.plugin = plugin  # The toy (plugin) we're going to play with
        self.data = data  # The toy's accessories (data for the plugin)
        self.shared_state = shared_state  # The playground rules (shared state for all plugins)
        self.stop_event = threading.Event()  # A bell to signal when playtime is over
        self.daemon = True  # This makes sure the thread stops when the main program stops

    def run(self) -> None:
        """
        Step 1b: Let the Toy Play! 🎉 (Plugin Execution)

        Toy analogy: This is where we let our toy run and have fun on its track.

        Reality: This method executes the plugin's main functionality.
        We use a try-except block to catch and log any errors that occur during execution.
        """
        try:
            # Let the toy (plugin) play with its accessories (data) following the playground rules (shared state)
            self.plugin.execute(self.data, self.shared_state)
        except Exception as e:
            # If the toy breaks (an error occurs), we log what happened
            logger.error(f"Uh oh! Plugin {self.plugin.__name__} had a problem: {e}")

    def stop(self) -> None:
        """
        Step 1c: Nap Time for Toys 😴 (Thread Termination)

        Toy analogy: When it's time to rest, we gently tell our toy to stop playing.

        Reality: This method sets a flag to signal the thread to terminate its execution.
        """
        # Ring the bell to signal that playtime is over
        self.stop_event.set()

"""
Step 2: The Toy Box Manager 📦 (Plugin Management)

Toy analogy: This is like a friendly robot that helps you manage all your toys.

Reality: The PluginManager class is responsible for loading, starting, stopping,
and reloading plugins. It keeps track of all active plugins and their threads.
"""
class PluginManager:

    def __init__(self, plugin_dir: str):
        """
        Step 2a: Setting Up the Toy Box

        Toy analogy: Setting up our toy box. 

        Reality: We're initializing the PluginManager with the directory where plugins are stored.
        """
        self.plugin_dir = plugin_dir  # The shelf where we keep our toys (plugins)
        self.plugins: Dict[str, Any] = {}  # A list of all our toys
        self.plugin_threads: Dict[str, PluginThread] = {}  # Toys currently playing on their tracks
        self.lock = threading.Lock()  # A special lock to make sure we don't mess up our toy collection
        self.observer: Observer = None  # Our toy box watcher (file system observer)

    def load_plugins(self) -> None:
        """
        Step 2b: Unpacking the Toy Box 🧸 (Plugin Discovery)

        Toy analogy: We open the toy box and look at all the toys we have.

        Reality: This method scans the plugin directory and attempts to load each .py file as a plugin.
        """
        with self.lock:  # Make sure no one messes with our toy box while we're looking inside
            for filename in os.listdir(self.plugin_dir):
                if filename.endswith(".py"):
                    plugin_name = filename[:-3]  # Remove the .py extension
                    self.load_plugin(plugin_name)  # Load each toy (plugin) we find

    def load_plugin(self, plugin_name: str) -> None:
        """
        Step 2c: Getting a Toy Ready 🔧 (Plugin Loading)

        Toy analogy: We take a toy out of the box and make sure it's ready to play.

        Reality: This method dynamically imports a plugin module and checks if it has the required 'execute' function.
        """
        try:
            module_name = f"plugins.{plugin_name}"
            module_path = os.path.join(self.plugin_dir, f"{plugin_name}.py")
            
            # Use Python's magic to make the toy work (import the plugin)
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Check if the toy has all its parts (the 'execute' function)
            if hasattr(module, 'execute'):
                self.plugins[plugin_name] = module
                logger.info(f"Yay! We got {plugin_name} ready to play!")
            else:
                logger.warning(f"Oh no! {plugin_name} is missing some parts. It can't play.")
        except Exception as e:
            logger.error(f"Oops! We couldn't get {plugin_name} ready. Here's why: {e}")

    def start_plugin_thread(self, plugin_name: str) -> None:
        """
        Step 2d: Playtime Begins! 🎮 (Thread Initialization)

        Toy analogy: We put a toy on its special track and say "Go! Have fun!"

        Reality: This method creates and starts a new thread for a specific plugin.
        """
        if plugin_name not in self.plugins:
            logger.warning(f"{plugin_name} is not in our toy box. We can't start it.")
            return
        
        plugin = self.plugins[plugin_name]
        thread = PluginThread(plugin, {'name': 'World'}, shared_state)
        thread.start()
        self.plugin_threads[plugin_name] = thread
        logger.info(f"{plugin_name} is now playing on its track!")

    def stop_plugin_thread(self, plugin_name: str) -> None:
        """
        Step 2e: Cleanup Time 🧹 (Thread Termination)

        Toy analogy: When you're done playing with a toy, we help put it away nicely.

        Reality: This method stops the execution of a plugin's thread and removes it from the active threads.
        """
        if plugin_name in self.plugin_threads:
            thread = self.plugin_threads[plugin_name]
            thread.stop()
            thread.join(timeout=1)
            del self.plugin_threads[plugin_name]
            logger.info(f"{plugin_name} is now resting in the toy box.")

    def reload_plugin(self, plugin_name: str) -> None:
        """
        Step 2f: Toy Makeover ✨ (Plugin Reloading)

        Toy analogy: Sometimes we can make old toys feel like new!

        Reality: This method reloads a plugin by stopping its current thread, reimporting the module,
        and starting a new thread with the updated code.
        """
        with self.lock:
            try:
                self.stop_plugin_thread(plugin_name)
                
                module_name = f"plugins.{plugin_name}"
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    importlib.reload(module)
                    self.plugins[plugin_name] = module
                else:
                    self.load_plugin(plugin_name)
                
                logger.info(f"{plugin_name} got a makeover and is ready to play again!")
            except Exception as e:
                logger.error(f"Oops! We couldn't give {plugin_name} a makeover. Here's why: {e}")

    def start_watchdog(self) -> None:
        """
        Step 2g: The Toy Guardian 🐶 (File System Watcher)

        Toy analogy: We have a special puppy that watches the toy box.

        Reality: This method starts a file system observer that monitors the plugin directory for changes.
        """
        event_handler = PluginReloader(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.plugin_dir, recursive=False)
        self.observer.start()
        logger.info("Our toy box watcher is now on duty!")

    def stop_watchdog(self) -> None:
        """
        Step 2h: Puppy Nap Time 🐾 (Stopping File System Watcher)

        Toy analogy: When we're done playing, we let our watchdog puppy take a nap.

        Reality: This method stops the file system observer when it's no longer needed.
        """
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=1)
            logger.info("Our toy box watcher is taking a nap.")

    def cleanup(self) -> None:
        """
        Step 2i: The Big Cleanup 🧼 (Resource Management)

        Toy analogy: Before we go to bed, we make sure all toys are put away nicely.

        Reality: This method ensures all plugin threads are stopped and resources are properly released.
        """
        self.stop_watchdog()
        for plugin_name in list(self.plugin_threads.keys()):
            self.stop_plugin_thread(plugin_name)
        logger.info("All toys are now resting in the toy box.")

    def handle_plugin_change(self, plugin_file):
        """
        Step 2j: Toy Upgrade Alert! 🚨 (Plugin Update Handler)

        Toy analogy: When a toy gets an upgrade, we quickly swap it with the old one.

        Reality: This method is called when a plugin file is modified, triggering a reload of the plugin.
        """
        plugin_name = plugin_file.split('.')[0]  # Remove the file extension
        self.reload_plugin(plugin_name)

"""
Step 3: The Toy Upgrade Detector 🕵️‍♂️ (File Change Handler)

Toy analogy: This is like a detective that notices when toys get upgrades.

Reality: This class extends FileSystemEventHandler to detect changes in plugin files.
"""
class PluginReloader(FileSystemEventHandler):

    def __init__(self, plugin_manager: PluginManager):
        """
        Step 3a: Giving the Detective a Walkie-Talkie

        Toy analogy: We give our detective a walkie-talkie to talk to the Toy Box Manager.

        Reality: We're passing a reference to the PluginManager for communication.
        """
        self.plugin_manager = plugin_manager  # Our walkie-talkie to the Toy Box Manager

    def on_modified(self, event):
        """
        Step 3b: Upgrade Spotted! 📢 (File Modification Event)

        Toy analogy: When the detective sees a toy change, it shouts "Upgrade!" into the walkie-talkie.

        Reality: This method is called when a file in the plugin directory is modified,
        triggering the plugin manager to reload the affected plugin.
        """
        if event.src_path.endswith(".py"):
            plugin_name = os.path.basename(event.src_path)[:-3]  # Get the toy's name (remove .py)
            logger.info(f"Wow! {event.src_path} got an upgrade!")
            self.plugin_manager.reload_plugin(plugin_name)  # Tell the manager to update the toy

# This PluginManager system allows for dynamic loading, unloading, and reloading of plugins,
# enabling a flexible and extensible application architecture.
