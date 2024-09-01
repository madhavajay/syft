from unittest.mock import MagicMock, patch

import pytest

from .setup import execute


@pytest.fixture
def mock_shared_state():
    mock = MagicMock()
    mock.request_config.side_effect = lambda key, callback, namespace: callback(key)
    return mock


@pytest.fixture
def mock_input(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("builtins.input", mock)
    return mock


@pytest.fixture
def mock_os_makedirs(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("os.makedirs", mock)
    return mock


def test_execute_default_path(
    mock_shared_state, mock_input, mock_os_makedirs, tmp_path
):
    mock_input.return_value = ""

    with patch("os.path.expanduser") as mock_expanduser:
        mock_expanduser.return_value = str(tmp_path / "Desktop/SyftBox")
        result = execute({}, mock_shared_state)

    assert result == str(tmp_path / "Desktop/SyftBox")
    mock_os_makedirs.assert_called_once_with(
        str(tmp_path / "Desktop/SyftBox"), exist_ok=True
    )


def test_execute_custom_path(mock_shared_state, mock_input, mock_os_makedirs, tmp_path):
    custom_path = str(tmp_path / "CustomSyftBox")
    mock_input.return_value = custom_path

    with patch("os.path.isdir", return_value=True):
        result = execute({}, mock_shared_state)

    assert result == custom_path
    mock_os_makedirs.assert_called_once_with(custom_path, exist_ok=True)


def test_execute_invalid_then_valid_path(
    mock_shared_state, mock_input, mock_os_makedirs, tmp_path
):
    invalid_path = "/invalid/path"
    valid_path = str(tmp_path / "ValidSyftBox")
    mock_input.side_effect = [invalid_path, valid_path]

    with patch("os.path.isdir", side_effect=[False, True]):
        result = execute({}, mock_shared_state)

    assert result == valid_path
    mock_os_makedirs.assert_called_once_with(valid_path, exist_ok=True)
    assert mock_input.call_count == 2


def test_execute_max_attempts_reached(
    mock_shared_state, mock_input, mock_os_makedirs, tmp_path
):
    invalid_paths = ["/invalid/path1", "/invalid/path2", "/invalid/path3"]
    mock_input.side_effect = invalid_paths

    with patch("os.path.isdir", return_value=False), patch(
        "os.path.expanduser"
    ) as mock_expanduser:
        mock_expanduser.return_value = str(tmp_path / "Desktop/SyftBox")
        result = execute({}, mock_shared_state)

    assert result == str(tmp_path / "Desktop/SyftBox")
    mock_os_makedirs.assert_called_once_with(
        str(tmp_path / "Desktop/SyftBox"), exist_ok=True
    )
    assert mock_input.call_count == 3


@pytest.mark.parametrize(
    "error,expected_log",
    [
        (PermissionError, "Failed to set SyftBox Folder. Error: "),
        (OSError, "Failed to set SyftBox Folder. Error: "),
    ],
)
def test_execute_error_handling(
    mock_shared_state, mock_input, mock_os_makedirs, caplog, error, expected_log
):
    mock_input.return_value = "/some/path"

    with patch("os.path.isdir", return_value=True):
        mock_os_makedirs.side_effect = error("Test error")

        with pytest.raises(error):
            execute({}, mock_shared_state)

    assert expected_log in caplog.text
    assert "Test error" in caplog.text


def test_execute_eof_error(mock_shared_state, mock_input, mock_os_makedirs, tmp_path):
    mock_input.side_effect = EOFError()

    with patch("os.path.expanduser") as mock_expanduser:
        mock_expanduser.return_value = str(tmp_path / "Desktop/SyftBox")
        result = execute({}, mock_shared_state)

    assert result == str(tmp_path / "Desktop/SyftBox")
    mock_os_makedirs.assert_called_once_with(
        str(tmp_path / "Desktop/SyftBox"), exist_ok=True
    )
    assert mock_input.call_count == 1
