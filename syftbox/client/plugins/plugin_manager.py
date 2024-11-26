from typing import Optional

from syftbox.client.exceptions import SyftPluginException
from syftbox.client.plugins.apps import AppRunner
from syftbox.client.plugins.sync.manager import SyncManager


class PluginManager:
    def __init__(
        self,
        sync_manager: Optional[SyncManager] = None,
        app_runner: Optional[AppRunner] = None,
    ):
        self.__sync_manager = sync_manager
        self.__app_runner = app_runner

    @property
    def sync_manager(self) -> SyncManager:
        if self.__sync_manager is None:
            raise SyftPluginException("SyncManager not initialized")
        return self.__sync_manager

    @property
    def app_runner(self) -> AppRunner:
        if self.__app_runner is None:
            raise SyftPluginException("AppRunner not initialized")
        return self.__app_runner
