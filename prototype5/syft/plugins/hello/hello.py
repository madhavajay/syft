import time
from typing import Any, Dict


def execute(data: Dict[str, Any], shared_state: Any) -> None:
    """
    Execute function for the Hello World plugin.
    This function will print "Hello World" every second.
    """
    while True:
        print("Hello World!")
        time.sleep(1)


# This plugin doesn't need to return anything, so we don't include a return statement.
