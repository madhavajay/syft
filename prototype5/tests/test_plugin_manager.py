import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syft.plugin_manager import PluginManager, PluginThread, PluginReloader
import logging
import tempfile
import os
from watchdog.events import FileModifiedEvent

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

def test_execute_plugins(plugin_manager, caplog):
    # Create mock plugins
    mock_plugin1 = Mock()
    mock_plugin2 = Mock()
    mock_plugin3 = Mock()

    # Set up the plugins dictionary
    plugin_manager.plugins = {
        'plugin1': mock_plugin1,
        'plugin2': mock_plugin2,
        'plugin3': mock_plugin3
    }

    # Make plugin2 raise an exception when executed
    mock_plugin2.execute.side_effect = Exception("Test exception")

    # Execute the plugins
    with caplog.at_level(logging.INFO):
        plugin_manager.execute_plugins()

    # Assert that all plugins were called with correct arguments
    mock_plugin1.execute.assert_called_once_with({}, plugin_manager.shared_state)
    mock_plugin2.execute.assert_called_once_with({}, plugin_manager.shared_state)
    mock_plugin3.execute.assert_called_once_with({}, plugin_manager.shared_state)

    # Check that the execution messages for all plugins were logged
    assert "Executing plugin: plugin1" in caplog.text
    assert "Executing plugin: plugin2" in caplog.text
    assert "Executing plugin: plugin3" in caplog.text

    # Check that the error for plugin2 was logged
    assert "Error executing plugin plugin2: Test exception" in caplog.text

def test_on_modified(plugin_manager):
    """Test that on_modified function properly detects file modifications."""
    # Create a temporary directory and file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = os.path.join(temp_dir, "test_plugin.py")
        with open(temp_file, "w") as f:
            f.write("def execute(): pass")
        
        # Set up the plugin manager
        plugin_manager.plugin_dir = temp_dir
        plugin_manager.load_plugin(temp_file)
        
        # Create a PluginReloader instance
        reloader = PluginReloader(plugin_manager)
        
        # Mock the reload_plugin method
        with patch.object(plugin_manager, 'reload_plugin') as mock_reload:
            # Simulate a file modification event
            event = FileModifiedEvent(temp_file)
            reloader.on_modified(event)
            
            # Check if reload_plugin was called with the correct plugin name
            mock_reload.assert_called_once_with("test_plugin")

        # Modify the file
        with open(temp_file, "a") as f:
            f.write("\ndef new_function(): pass")
        
        # Simulate another file modification event
        with patch.object(plugin_manager, 'reload_plugin') as mock_reload:
            event = FileModifiedEvent(temp_file)
            reloader.on_modified(event)
            
            # Check if reload_plugin was called again
            mock_reload.assert_called_once_with("test_plugin")

        # Test with a non-Python file
        non_python_file = os.path.join(temp_dir, "not_a_plugin.txt")
        with open(non_python_file, "w") as f:
            f.write("This is not a Python file")
        
        with patch.object(plugin_manager, 'reload_plugin') as mock_reload:
            event = FileModifiedEvent(non_python_file)
            reloader.on_modified(event)
            
            # Check that reload_plugin was not called
            mock_reload.assert_not_called()

def test_handle_plugin_change(plugin_manager):
    """Test that handle_plugin_change is called and triggers a plugin reload when a file is modified."""
    # Create a temporary directory and file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = os.path.join(temp_dir, "test_plugin.py")
        with open(temp_file, "w") as f:
            f.write("def execute(data, shared_state): pass")
        
        # Set up the plugin manager
        plugin_manager.plugin_dir = temp_dir
        plugin_manager.load_plugin(temp_file)
        
        # Mock the reload_plugin method
        with patch.object(plugin_manager, 'reload_plugin') as mock_reload:
            # Call handle_plugin_change
            plugin_manager.handle_plugin_change("test_plugin.py")
            
            # Check if reload_plugin was called with the correct plugin name
            mock_reload.assert_called_once_with("test_plugin")

        # Test with a non-Python file
        non_python_file = "not_a_plugin.txt"
        
        with patch.object(plugin_manager, 'reload_plugin') as mock_reload:
            plugin_manager.handle_plugin_change(non_python_file)
            
            # Check that reload_plugin was not called
            mock_reload.assert_not_called()

        # Test with a Python file that's not loaded as a plugin
        unloaded_plugin = "unloaded_plugin.py"
        
        with patch.object(plugin_manager, 'reload_plugin') as mock_reload:
            plugin_manager.handle_plugin_change(unloaded_plugin)
            
            # Check that reload_plugin was called, even if the plugin wasn't previously loaded
            mock_reload.assert_called_once_with("unloaded_plugin")

    # Test integration with PluginReloader
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = os.path.join(temp_dir, "test_plugin.py")
        with open(temp_file, "w") as f:
            f.write("def execute(data, shared_state): pass")
        
        plugin_manager.plugin_dir = temp_dir
        plugin_manager.load_plugin(temp_file)
        
        reloader = PluginReloader(plugin_manager)
        
        with patch.object(plugin_manager, 'handle_plugin_change') as mock_handle_change:
            event = FileModifiedEvent(temp_file)
            reloader.on_modified(event)
            
            # Check if handle_plugin_change was called with the correct filename
            mock_handle_change.assert_called_once_with("test_plugin.py")

def test_reload_plugin_module_reload(plugin_manager):
    # Setup
    plugin_name = "test_plugin"
    module_name = f"plugins.{plugin_name}"
    mock_module = MagicMock()
    
    # Mock sys.modules to include our test module
    with patch.dict(sys.modules, {module_name: mock_module}):
        # Mock importlib.reload
        with patch('importlib.reload') as mock_reload:
            # Call the method
            plugin_manager.reload_plugin(plugin_name)
            
            # Assertions
            mock_reload.assert_called_once_with(mock_module)
            assert plugin_manager.plugins[plugin_name] == mock_module

    # Verify that the plugin was added to the plugins dictionary
    assert plugin_name in plugin_manager.plugins

def test_start_plugin_thread_nonexistent_plugin(plugin_manager, caplog):
    # Setup
    non_existent_plugin = "imaginary_plugin"
    
    # Ensure the plugin is not in the toy box
    assert non_existent_plugin not in plugin_manager.plugins
    
    # Capture logs at WARNING level
    with caplog.at_level(logging.WARNING):
        # Call the method
        plugin_manager.start_plugin_thread(non_existent_plugin)
    
    # Assertions
    expected_message = f"{non_existent_plugin} is not in our toy box. We can't start it."
    assert any(expected_message in record.message for record in caplog.records), \
        f"Expected warning message not found in logs: {caplog.text}"
    
    # Verify that no thread was started
    assert non_existent_plugin not in plugin_manager.plugin_threads

    # Verify that the method returned early
    assert len(plugin_manager.plugin_threads) == 0

def test_load_plugins():
    # Create a mock plugin directory structure
    mock_file_structure = {
        'plugins': {
            'plugin1.py': '',
            'plugin2.py': '',
            '__init__.py': '',
            'subdir': {
                'plugin3.py': '',
                'not_a_plugin.txt': ''
            }
        }
    }

    # Mock os.walk to return our mock file structure
    def mock_walk(path):
        if path == './plugins':
            yield './plugins', ['subdir'], ['plugin1.py', 'plugin2.py', '__init__.py']
            yield './plugins/subdir', [], ['plugin3.py', 'not_a_plugin.txt']

    # Create a PluginManager instance
    plugin_manager = PluginManager('./plugins')

    # Mock the necessary functions and methods
    with patch('os.walk', mock_walk), \
         patch('os.path.join', os.path.join), \
         patch.object(plugin_manager, 'load_plugin') as mock_load_plugin, \
         patch.object(plugin_manager, 'lock') as mock_lock:

        # Call the method we're testing
        plugin_manager.load_plugins()

        # Assert that the lock was used
        mock_lock.__enter__.assert_called_once()
        mock_lock.__exit__.assert_called_once()

        # Assert that load_plugin was called for each .py file (excluding __init__.py)
        mock_load_plugin.assert_any_call(os.path.join('./plugins', 'plugin1.py'))
        mock_load_plugin.assert_any_call(os.path.join('./plugins', 'plugin2.py'))
        mock_load_plugin.assert_any_call(os.path.join('./plugins/subdir', 'plugin3.py'))
        
        # Assert that load_plugin was called exactly 3 times
        assert mock_load_plugin.call_count == 3

        # Assert that load_plugin was not called for __init__.py or not_a_plugin.txt
        assert os.path.join('./plugins', '__init__.py') not in [call[0][0] for call in mock_load_plugin.call_args_list]
        assert os.path.join('./plugins/subdir', 'not_a_plugin.txt') not in [call[0][0] for call in mock_load_plugin.call_args_list]


