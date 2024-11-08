from pathlib import Path

import pytest

from syftbox.lib.client_shim import SyftClientConfig


@pytest.fixture
def mocked_config(monkeypatch, tmp_path):
    config_path = Path(tmp_path, "config.json")
    data_dir = Path(tmp_path)
    conf = SyftClientConfig(
        path=config_path,
        data_dir=data_dir,
        email="test@openmined.org",
        client_url="http://test:8080",
    )
    conf.save()
    conf.data_dir.mkdir(parents=True, exist_ok=True)

    def mock_load(*args, **kwargs):
        nonlocal conf
        return conf

    monkeypatch.setattr(SyftClientConfig, "load", mock_load)

    yield conf

    monkeypatch.undo()
