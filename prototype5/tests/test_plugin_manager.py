import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syft.plugin_manager import PluginManager, PluginThread, PluginReloader

@pytest.fixture
def plugin_manager():
    """Fixture for creating a PluginManager instance."""
    with patch('syft.plugin_manager.Observer'):
        pm = PluginManager('./plugins')
        yield pm
        pm.cleanup()

def test_load_plugin(plugin_manager, tmp_path):
    """Test loading a plugin."""
    plugin_file = tmp_path / "test_plugin.py"
    plugin_file.write_text("""
def execute(data, shared_state):
    print("Hello, World!")
""")

    plugin_manager.plugin_dir = str(tmp_path)
    # Use the full path to the plugin file
    plugin_manager.load_plugin(str(plugin_file))

    assert "test_plugin" in plugin_manager.plugins
    assert hasattr(plugin_manager.plugins["test_plugin"], "execute")

def test_start_plugin_thread(plugin_manager):
    """Test starting a plugin thread."""
    mock_plugin = Mock()
    plugin_manager.plugins["test_plugin"] = mock_plugin

    plugin_manager.start_plugin_thread("test_plugin")

    assert "test_plugin" in plugin_manager.plugin_threads
    assert isinstance(plugin_manager.plugin_threads["test_plugin"], PluginThread)

def test_stop_plugin_thread(plugin_manager):
    """Test stopping a plugin thread."""
    mock_thread = Mock()
    plugin_manager.plugin_threads["test_plugin"] = mock_thread

    plugin_manager.stop_plugin_thread("test_plugin")

    mock_thread.stop.assert_called_once()
    mock_thread.join.assert_called_once_with(timeout=1)
    assert "test_plugin" not in plugin_manager.plugin_threads

def test_start_watchdog(plugin_manager):
    """Test starting the watchdog."""
    with patch('syft.plugin_manager.Observer') as mock_observer:
        plugin_manager.start_watchdog()

    mock_observer.return_value.start.assert_called_once()

def test_stop_watchdog(plugin_manager):
    """Test stopping the watchdog."""
    mock_observer = Mock()
    plugin_manager.observer = mock_observer

    plugin_manager.stop_watchdog()

    mock_observer.stop.assert_called_once()
    mock_observer.join.assert_called_once()

def test_cleanup(plugin_manager):
    """Test cleanup method."""
    mock_thread1 = Mock()
    mock_thread2 = Mock()
    plugin_manager.plugin_threads = {
        "plugin1": mock_thread1,
        "plugin2": mock_thread2
    }

    with patch.object(plugin_manager, 'stop_watchdog') as mock_stop_watchdog:
        plugin_manager.cleanup()

    mock_thread1.stop.assert_called_once()
    mock_thread2.stop.assert_called_once()
    mock_stop_watchdog.assert_called_once()

def test_load_plugin_no_execute(plugin_manager, tmp_path):
    """Test loading a plugin without an execute function."""
    plugin_file = tmp_path / "no_execute_plugin.py"
    plugin_file.write_text("def some_function(): pass")

    plugin_manager.plugin_dir = str(tmp_path)
    plugin_manager.load_plugin("no_execute_plugin")

    assert "no_execute_plugin" not in plugin_manager.plugins

def test_load_plugin_exception(plugin_manager, tmp_path):
    """Test loading a plugin that raises an exception."""
    plugin_file = tmp_path / "exception_plugin.py"
    plugin_file.write_text("raise ImportError('Test error')")

    plugin_manager.plugin_dir = str(tmp_path)
    plugin_manager.load_plugin("exception_plugin")

    assert "exception_plugin" not in plugin_manager.plugins

def test_reload_plugin_not_loaded(plugin_manager):
    """Test reloading a plugin that hasn't been loaded."""
    with patch('importlib.reload') as mock_reload:
        plugin_manager.reload_plugin("non_existent_plugin")
    
    mock_reload.assert_not_called()

def test_reload_plugin_exception(plugin_manager):
    """Test reloading a plugin that raises an exception."""
    mock_plugin = MagicMock()
    plugin_manager.plugins["test_plugin"] = mock_plugin

    with patch('importlib.reload', side_effect=ImportError('Test error')):
        plugin_manager.reload_plugin("test_plugin")

    assert "test_plugin" in plugin_manager.plugins

