import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = 3000  # Run every 3 seconds by default
DESCRIPTION = "A plugin that ensures both the SyftBox and Syft folders are initialized."

def run(shared_state):
    # Initialize SyftBox folder
    syftbox_folder = shared_state.get('syftbox_folder')
    
    if not syftbox_folder:
        logger.warning("syftbox_folder is not set in shared state")
    else:
        if not os.path.exists(syftbox_folder):
            try:
                os.makedirs(syftbox_folder)
                logger.info(f"Created SyftBox folder: {syftbox_folder}")
            except Exception as e:
                logger.error(f"Failed to create SyftBox folder: {syftbox_folder}. Error: {str(e)}")
        else:
            logger.debug(f"SyftBox folder exists: {syftbox_folder}")

    # Initialize Syft folder
    syft_folder = shared_state.get('syft_folder')
    
    if not syft_folder:
        logger.warning("syft_folder is not set in shared state")
    else:
        if not os.path.exists(syft_folder):
            try:
                os.makedirs(syft_folder)
                logger.info(f"Created Syft folder: {syft_folder}")
            except Exception as e:
                logger.error(f"Failed to create Syft folder: {syft_folder}. Error: {str(e)}")
        else:
            logger.debug(f"Syft folder exists: {syft_folder}")
