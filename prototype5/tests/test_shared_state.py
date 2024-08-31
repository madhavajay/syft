import pytest
from syft.shared_state import SharedState

@pytest.fixture
def shared_state():
    return SharedState()

def test_set_and_get(shared_state):
    shared_state.set("test_key", "test_value")
    assert shared_state.get("test_key") == "test_value"

def test_get_with_default(shared_state):
    assert shared_state.get("non_existent_key", default="default_value") == "default_value"

def test_request_config(shared_state):
    def mock_prompt(key):
        return "prompted_value"

    value = shared_state.request_config("test_key", mock_prompt)
    assert value == "prompted_value"
    assert shared_state.get("test_key") == "prompted_value"

# Add more tests...