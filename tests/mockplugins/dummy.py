from time import time

DEFAULT_SCHEDULE = 1000
DESCRIPTION = "A dummy plugin for testing"


def run(shared_state, *args, **kwargs):
    if kwargs.get("raise_exception"):
        print("Dummy plugin raised an error", args, kwargs)
        raise Exception("Dummy plugin raised an error")

    print("Dummy plugin ran successfully", args, kwargs)
    return {
        "ts": time(),
        "args": args,
        "kwargs": kwargs,
    }
