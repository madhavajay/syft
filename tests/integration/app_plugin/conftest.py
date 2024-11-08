# conftest.py
import shutil
import tempfile

import pytest

from syftbox.lib.client_config import SyftClientConfig
from syftbox.lib.workspace import SyftWorkspace


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    temp_root_dir = tempfile.mkdtemp()
    workspace = SyftWorkspace(data_dir=temp_root_dir)
    workspace.mkdirs()

    yield workspace
    shutil.rmtree(workspace.root_dir)


@pytest.fixture
def test_client_config(temp_workspace: SyftWorkspace):
    """Create a test client configuration with temporary directories."""
    config_path = temp_workspace.data_dir / "config.json"

    config = SyftClientConfig(
        email="test@example.com",
        path=config_path,
        data_dir=temp_workspace.data_dir,
    )

    yield config


@pytest.fixture
def shared_state(test_client_config):
    """Create shared state for testing."""
    return SharedState(client_config=test_client_config)
