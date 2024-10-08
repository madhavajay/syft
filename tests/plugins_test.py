from pathlib import Path
from time import sleep

import pytest
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from syftbox.client.plugin import PluginManager, PluginStatus
from syftbox.lib.lib import ClientConfig, SharedState

_MOCK_PLUGINS_DIR = Path(__file__).parent / "mockplugins"


@pytest.fixture
def sqlscheduler(tmp_path):
    dbpath = tmp_path / "jobs.db"
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(SQLAlchemyJobStore(f"sqlite:///{dbpath}"), "default")
    return scheduler


@pytest.fixture
def tmp_shared_state(tmp_path):
    config = tmp_path / "config.json"
    sync_folder = tmp_path / "sync"
    sync_folder.mkdir()

    config = ClientConfig(config_path=config, sync_folder=sync_folder)
    return SharedState(config)


@pytest.fixture
def plugin_manager(tmp_shared_state, sqlscheduler):
    manager = PluginManager(
        tmp_shared_state,
        sqlscheduler,
        _MOCK_PLUGINS_DIR,
    )
    yield manager
    manager.stop()


def test_plugin_load(plugin_manager):
    plugin_manager.load()

    plugin = plugin_manager.get("dummy")
    assert plugin.name == "dummy"
    # set in dummpy.py
    assert plugin.schedule == 1000
    assert plugin.description == "A dummy plugin for testing"


def test_plugin_run(plugin_manager):
    plugin_manager.load()
    assert "dummy" in plugin_manager.loaded

    res = plugin_manager.run("dummy", 42, run_type="single run")
    assert res.status == PluginStatus.SUCCESS
    assert res.data["args"] == (42,)
    assert res.data["kwargs"] == {"run_type": "single run"}


def test_plugin_run_exception(plugin_manager):
    plugin_manager.load()
    assert "dummy" in plugin_manager.loaded

    with pytest.raises(Exception):
        plugin_manager.run("dummy", raise_exception=True, run_type="single run")


def test_plugin_schedule(plugin_manager):
    plugin_manager.load()
    assert "dummy" in plugin_manager.loaded

    # schedule the plugin
    result = plugin_manager.schedule("dummy", run_type="scheduled")
    assert result.status == PluginStatus.SUCCESS, f"{result.message} - {result.data}"

    # wait for the plugin to run atleast once
    sleep(1)

    # cleanup
    result = plugin_manager.unschedule("dummy")
    assert result.status == PluginStatus.SUCCESS, f"{result.message} - {result.data}"
    assert len(plugin_manager.running) == 0


def test_plugin_schedule_exception(plugin_manager):
    """
    Schedule a plugin that raises an error.
    Expectation is that scheduled function will fail, but not propagate the error upwards.
    We might want to change this behavior in the future.
    """

    # load plugins
    plugin_manager.load()
    assert "dummy" in plugin_manager.loaded

    # schedule the plugin
    result = plugin_manager.schedule(
        "dummy", raise_exception=True, run_type="scheduled"
    )
    assert result.status == PluginStatus.SUCCESS, f"{result.message} - {result.data}"

    # wait for the plugin to run atleast once
    sleep(1)

    # cleanup
    result = plugin_manager.unschedule("dummy")
    assert result.status == PluginStatus.SUCCESS, f"{result.message} - {result.data}"
    assert len(plugin_manager.running) == 0
