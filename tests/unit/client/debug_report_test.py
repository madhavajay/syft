from pathlib import Path

import pytest

from syftbox.lib import ClientConfig
from syftbox.lib.debug import debug_report, debug_report_yaml


@pytest.fixture
def mocked_config(monkeypatch, tmp_path):
    def mock_load(*args, **kwargs):
        config_path = Path(tmp_path, "config.json")
        sync_folder = Path(tmp_path, "sync")
        conf = ClientConfig(
            config_path=config_path,
            sync_folder=sync_folder,
            email="test@openmined.org",
        )
        conf.save()
        sync_folder.mkdir(parents=True, exist_ok=True)
        return conf

    monkeypatch.setattr(ClientConfig, "load", mock_load)

    yield

    monkeypatch.undo()


def test_debug_report(mocked_config):
    result = debug_report()
    assert isinstance(result, dict)
    assert "system" in result
    assert "syftbox" in result
    assert "syftbox_env" in result
    assert "resources" in result["system"]
    assert "operating_system" in result["system"]
    assert "python" in result["system"]
    assert "command" in result["syftbox"]
    assert "client_config_path" in result["syftbox"]
    assert "client_config" in result["syftbox"]
    assert "apps_dir" in result["syftbox"]
    assert "apps" in result["syftbox"]


def test_debug_report_readable(mocked_config):
    result = debug_report_yaml()
    assert isinstance(result, str)
    assert "system" in result
    assert "syftbox" in result
    assert "syftbox_env" in result
    assert "resources" in result
    assert "operating_system" in result
    assert "python" in result
    assert "command" in result
    assert "client_config_path" in result
    assert "client_config" in result
    assert "apps_dir" in result
    assert "apps" in result
