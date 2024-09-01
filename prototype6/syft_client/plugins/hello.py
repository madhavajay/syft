import logging

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = 3000  # Run every 3 seconds by default
DESCRIPTION = "A simple plugin that says hello and counts its runs."

def run(shared_state):
    count = shared_state.get('hello_count', 0)
    count += 1
    shared_state.set('hello_count', count)
    logger.info(f"Hello from the plugin! This is run number {count}")