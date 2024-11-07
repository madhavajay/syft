from pathlib import Path

import pytest

from syftbox.lib.lib import ClientConfig


@pytest.fixture
def mocked_config(monkeypatch, tmp_path):
    config_path = Path(tmp_path, "config.json")
    sync_folder = Path(tmp_path, "sync")
    conf = ClientConfig(
        config_path=config_path,
        sync_folder=sync_folder,
        email="test@openmined.org",
    )
    conf.save()
    sync_folder.mkdir(parents=True, exist_ok=True)

    def mock_load(*args, **kwargs):
        nonlocal conf
        return conf

    monkeypatch.setattr(ClientConfig, "load", mock_load)

    yield conf

    monkeypatch.undo()
