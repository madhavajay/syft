import importlib
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from time import time
from types import ModuleType
from typing import Any

from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import STATE_STOPPED

from syftbox.lib.lib import SharedState

__all__ = ["PluginManager", "PluginResult", "PluginStatus"]

_DEFAULT_PLUGINS_DIR = Path(__file__).parent / "plugins"


@dataclass
class Plugin:
    name: str
    module: ModuleType
    schedule: int
    description: str


@dataclass
class PluginJob:
    job: Job
    start_time: float
    schedule: int


class PluginStatus:
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class PluginResult:
    name: str
    status: PluginStatus
    message: str
    data: Any | Exception | None


class PluginManager:
    def __init__(
        self,
        shared_state: SharedState,
        scheduler: BackgroundScheduler,
        plugin_dir: Path = _DEFAULT_PLUGINS_DIR,
    ):
        self.shared_state = shared_state
        self.scheduler = scheduler
        self.plugin_dir = plugin_dir

        self._loaded: dict[str, Plugin] = {}
        self._running: dict[str, PluginJob] = {}
        self._started = False

    @property
    def running(self) -> dict[str, PluginJob]:
        return self._running

    @property
    def loaded(self) -> dict[str, Plugin]:
        return self._loaded

    def load(self):
        if self.scheduler.state == STATE_STOPPED:
            self.scheduler.start()
        self._load_plugins()

    def stop(self):
        if self.scheduler.state != STATE_STOPPED:
            self.unschedule_many(list(self._running.keys()))
            self.scheduler.remove_all_jobs()
            self.scheduler.shutdown()

        self._loaded = {}
        self._running = {}
        self._started = False

    def get(self, name: str) -> Plugin | None:
        return self._loaded.get(name)

    def schedule(
        self,
        name: str,
        *args,
        **kwargs,
    ) -> PluginResult:
        if name not in self._loaded:
            # error value return saying it's already loaded
            return PluginResult(
                name=name,
                status=PluginStatus.ERROR,
                message=f"Plugin {name} not found",
                data=None,
            )

        if self.scheduler.get_job(name):
            return PluginResult(
                name=name,
                status=PluginStatus.ERROR,
                message=f"Plugin {name} already running",
                data=None,
            )

        try:
            plugin = self._loaded[name]
            job: Job = self.scheduler.add_job(
                id=name,
                func=plugin.module.run,  # directly call the run function
                args=[
                    self.shared_state,
                    *args,
                ],  # pass shared_state as first arg
                kwargs=kwargs,
                trigger="interval",
                seconds=plugin.schedule / 1000,
            )
            self._running[name] = PluginJob(
                job=job,
                start_time=time(),
                schedule=plugin.schedule,
            )
            print("Started plugin:", name)
            return PluginResult(
                name=name,
                status=PluginStatus.SUCCESS,
                message=f"Plugin {name} scheduled",
                data=self._running[name],
            )
        except Exception as e:
            print(traceback.format_exc())
            return PluginResult(
                name=name,
                status=PluginStatus.ERROR,
                message=f"Error when scheduling plugin {name}",
                data=e,
            )

    def unschedule(self, name: str) -> PluginResult:
        if name not in self._running:
            return PluginResult(
                name=name,
                status=PluginStatus.ERROR,
                message=f"Plugin {name} is not running",
                data=None,
            )
        try:
            self.scheduler.remove_job(name)

            plugin = self._loaded[name]
            if hasattr(plugin.module, "stop"):
                plugin.module.stop()

            del self._running[name]
            return PluginResult(
                name=name,
                status=PluginStatus.SUCCESS,
                message=f"Plugin {name} unscheduled",
                data=None,
            )
        except Exception as e:
            print(traceback.format_exc())
            return PluginResult(
                name=name,
                status=PluginStatus.ERROR,
                message=f"Error when unscheduling plugin {name}",
                data=e,
            )

    def schedule_many(self, names: list[str], **kwargs) -> list[PluginResult]:
        return [self.schedule(name, **kwargs) for name in names]

    def unschedule_many(self, names: list[str]) -> list[PluginResult]:
        return [self.unschedule(name) for name in names]

    def run(self, name: str, *args, **kwargs) -> PluginResult:
        """Invoke a plugin's run function directly"""

        if name not in self._loaded:
            return PluginResult(
                name=name,
                status=PluginStatus.ERROR,
                message=f"Plugin {name} is not loaded",
                data=None,
            )

        module = self._loaded[name].module
        result = module.run(self.shared_state, *args, **kwargs)
        return PluginResult(
            name=name,
            status=PluginStatus.SUCCESS,
            message=f"Plugin {name} ran successfully",
            data=result,
        )

    def _load_plugins(self):
        if not self.plugin_dir.exists():
            print("plugins dir not found")
            return

        src_files = [
            src for src in self.plugin_dir.glob("*.py") if not src.name.startswith("__")
        ]

        sys.path.insert(0, str(self.plugin_dir.parent))

        for src in src_files:
            plugin_name = src.stem

            if plugin_name in self._loaded:
                print("plugin already loaded:", plugin_name)
                continue

            try:
                module = importlib.import_module(f"{src.parent.name}.{plugin_name}")

                # default schedule & description
                schedule = getattr(
                    module,
                    "DEFAULT_SCHEDULE",
                    5000,  # ms
                )
                description = getattr(
                    module,
                    "DESCRIPTION",
                    "No description available.",
                )
                print("loaded plugin:", plugin_name)
                plugin = Plugin(
                    name=plugin_name,
                    module=module,
                    schedule=schedule,
                    description=description,
                )
                self._loaded[plugin_name] = plugin
            except Exception:
                print(traceback.format_exc())
