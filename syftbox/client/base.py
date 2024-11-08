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
    """Configuration settings for the Syft client."""

    workspace: SyftWorkspace
    """Workspace instance managing data and computation."""

    server_client: httpx.Client

    @property
    def datasite(self) -> Path:
        """Path to the datasite directory for the current user."""
        ...
