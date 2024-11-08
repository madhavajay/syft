from pathlib import Path

import httpx
from typing_extensions import Protocol

from syftbox.lib.client_config import SyftClientConfig
from syftbox.lib.workspace import SyftWorkspace


class SyftClientInterface(Protocol):
    """
    Protocol defining the essential attributes required by SyftClient subsystems.

    This interface serves two main purposes:
    1. Prevents circular dependencies by providing a minimal interface that
       subsystems can import and type hint against, instead of importing
       the full SyftClient class.
    2. Enables dependency injection by defining a contract that any context
       or mock implementation can fulfill for testing or modular configuration.

    Attributes:
        config: Configuration settings for the Syft client
        workspace: Workspace instance managing data and computation
        server_client: HTTP client for server communication
    """

    config: SyftClientConfig
    workspace: SyftWorkspace
    server_client: httpx.Client


class SyftClientContext(SyftClientInterface):
    """
    Concrete implementation of SyftClientInterface that provides a lightweight
    context for subsystems.

    This class encapsulates the minimal set of attributes needed by subsystems
    without exposing the full SyftClient implementation.

    It will be instantiated by SyftClient, but sub-systems can freely pass it around.
    """

    def __init__(
        self,
        config: SyftClientConfig,
        workspace: SyftWorkspace,
        server_client: httpx.Client,
    ):
        self.config = config
        self.workspace = workspace
        self.server_client = server_client

    @property
    def datasites(self) -> Path:
        return self.workspace.datasites

    def __repr__(self) -> str:
        return f"SyftClientContext<{self.config.email}>"
