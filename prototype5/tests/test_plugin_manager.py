import pytest
from unittest.mock import Mock, patch
from plugin_manager import PluginManager, PluginThread

@pytest.fixture
def plugin_manager():
    """Fixture for creating a PluginManager instance."""
    with patch('plugin_manager.Observer'):
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
    plugin_manager.load_plugin("test_plugin")

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

def test_reload_plugin(plugin_manager, tmp_path):
    """Test reloading a plugin."""
    plugin_file = tmp_path / "test_plugin.py"
    plugin_file.write_text("""
def execute(data, shared_state):
    print("Hello, World!")
""")

    plugin_manager.plugin_dir = str(tmp_path)
    plugin_manager.load_plugin("test_plugin")
    
    plugin_file.write_text("""
def execute(data, shared_state):
    print("Hello, Updated World!")
""")
    
    plugin_manager.reload_plugin("test_plugin")
    
    assert "test_plugin" in plugin_manager.plugins
    assert hasattr(plugin_manager.plugins["test_plugin"], "execute")

def test_cleanup(plugin_manager):
    """Test cleanup of plugin threads."""
    mock_thread1 = Mock()
    mock_thread2 = Mock()
    plugin_manager.plugin_threads = {
        "plugin1": mock_thread1,
        "plugin2": mock_thread2
    }
    
    plugin_manager.cleanup()
    
    mock_thread1.stop.assert_called_once()
    mock_thread1.join.assert_called_once_with(timeout=1)
    mock_thread2.stop.assert_called_once()
    mock_thread2.join.assert_called_once_with(timeout=1)
    assert len(plugin_manager.plugin_threads) == 0