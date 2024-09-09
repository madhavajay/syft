import ctypes
import importlib
import inspect  # Add this import
import logging
import os
import threading
import time
from typing import Any, Callable, Dict

from syft.shared_state import shared_state
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


def _async_raise(tid, exctype):
    """Raises an exception in the threads with id tid"""
    if not inspect.isclass(exctype):
        raise TypeError("Only types can be raised (not instances)")
    if tid is not None:
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_long(tid), ctypes.py_object(exctype)
        )
    else:
        res = 0

    if res == 0:
        ""
        # raise ValueError("Invalid thread id")
    elif res != 1:
        # "if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


class PluginThread(threading.Thread):
    def _get_id(self):
        # returns id of the respective thread
        if hasattr(self, "_thread_id"):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id

    def raise_exception(self):
        thread_id = self._get_id()
        _async_raise(thread_id, SystemExit)


class PluginManager:
    def __init__(self, plugins_dir: str):
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, Any] = {}
        self.threads: Dict[str, PluginThread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        self.observer: Observer = Observer()

    def load_plugins(self) -> None:
        for item in os.listdir(self.plugins_dir):
            if os.path.isdir(
                os.path.join(self.plugins_dir, item)
            ) and not item.startswith("__"):
                self._load_plugin(item)

    def _load_plugin(self, plugin_name: str) -> None:
        try:
            module = importlib.import_module(
                f"syft.plugins.{plugin_name}.{plugin_name}"
            )
            self.plugins[plugin_name] = module
            logger.info(f"Loaded plugin: {plugin_name}")
        except ImportError as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")

    def execute_plugins(self) -> None:
        for plugin_name in self.plugins:
            module = self.plugins[plugin_name]

            if hasattr(module, "get_user_input"):
                module.get_user_input({}, shared_state)

        for plugin_name in self.plugins:
            self._start_plugin_thread(plugin_name)

    def _start_plugin_thread(
        self, plugin_name: str, skip_user_input: bool = False
    ) -> None:
        self._stop_plugin_thread(plugin_name)

        module = self.plugins[plugin_name]

        if hasattr(module, "execute"):
            stop_event = threading.Event()
            self.stop_events[plugin_name] = stop_event
            thread = PluginThread(
                target=self._run_plugin,
                args=(plugin_name, module.execute, stop_event),
                daemon=True,
            )
            self.threads[plugin_name] = thread
            thread.start()
            logger.info(f"Started thread for plugin: {plugin_name}")

    def _stop_plugin_thread(self, plugin_name: str) -> None:
        if plugin_name in self.stop_events:
            self.stop_events[plugin_name].set()
            if plugin_name in self.threads:
                thread = self.threads[plugin_name]
                thread.raise_exception()
                thread.join(timeout=5)
                if thread.is_alive():
                    logger.warning(f"Failed to stop thread for plugin: {plugin_name}")
                else:
                    logger.info(f"Stopped thread for plugin: {plugin_name}")
                del self.threads[plugin_name]
            del self.stop_events[plugin_name]

    def _run_plugin(
        self,
        plugin_name: str,
        execute_func: Callable[..., Any],
        stop_event: threading.Event,
    ) -> None:
        try:
            execute_func({}, shared_state)
        except SystemExit:
            logger.info(f"Plugin {plugin_name} thread was terminated")
        except Exception as e:
            logger.error(f"Error in plugin {plugin_name}: {e}")
        finally:
            if not stop_event.is_set():
                logger.info(
                    f"Plugin {plugin_name} has stopped unexpectedly (probably because the execute() method finished. If you don't want this to happen, add a while:True loop.)"
                )
                time.sleep(1)
                self._run_plugin(
                    plugin_name=plugin_name,
                    execute_func=execute_func,
                    stop_event=stop_event,
                )

    def start_watchdog(self) -> None:
        event_handler = PluginReloader(self)
        self.observer.schedule(event_handler, self.plugins_dir, recursive=True)
        self.observer.start()

    def cleanup(self) -> None:
        for plugin_name in list(self.stop_events.keys()):
            self._stop_plugin_thread(plugin_name)
        self.observer.stop()
        self.observer.join()


class PluginReloader(FileSystemEventHandler):
    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager

    def on_modified(self, event):
        if event.is_directory:
            return
        path_parts = event.src_path.split(os.path.sep)
        if "plugins" in path_parts:
            plugin_name = path_parts[path_parts.index("plugins") + 1]
            if plugin_name in self.plugin_manager.plugins:
                logger.info(f"Reloading plugin: {plugin_name}")
                self._reload_plugin(plugin_name)

    def _reload_plugin(self, plugin_name: str) -> None:
        # Stop the existing plugin thread
        self.plugin_manager._stop_plugin_thread(plugin_name)

        # Reload the plugin module
        try:
            module = self.plugin_manager.plugins[plugin_name]
            importlib.reload(module)
            self.plugin_manager.plugins[plugin_name] = module
            logger.info(f"Reloaded plugin: {plugin_name}")

            # Start the plugin in a new thread
            self.plugin_manager._start_plugin_thread(plugin_name, skip_user_input=True)
        except ImportError as e:
            logger.error(f"Failed to reload plugin {plugin_name}: {e}")
