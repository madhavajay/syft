import pytest
from unittest.mock import patch, MagicMock
from main import main

@pytest.fixture
def mock_plugin_manager():
    with patch('main.PluginManager') as mock:
        instance = mock.return_value
        yield mock
        # Ensure cleanup is called after the test
        instance.cleanup.assert_called_once()

def test_main_flow(mock_plugin_manager, capsys):
    # Mock time.sleep to raise KeyboardInterrupt on the first call
    mock_sleep = MagicMock(side_effect=[KeyboardInterrupt, None])
    
    with patch('main.time.sleep', mock_sleep):
        main()

    mock_plugin_manager.return_value.load_plugins.assert_called_once()
    mock_plugin_manager.return_value.start_watchdog.assert_called_once()
    mock_plugin_manager.return_value.cleanup.assert_called_once()

    captured = capsys.readouterr()
    assert "Alright, alright, I'll stop. Sheesh." in captured.out

# Add more tests...