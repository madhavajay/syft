import logging
import os
import shutil
import json

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = 3000  # Run every 3 seconds by default
DESCRIPTION = "A plugin that synchronizes datasite folders between Syft and SyftBox folders."

def run(shared_state):
    syft_folder = shared_state.get('syft_folder')
    syftbox_folder = shared_state.get('syftbox_folder')

    if not syft_folder or not syftbox_folder:
        logger.warning("syft_folder or syftbox_folder is not set in shared state")
        return

    if not os.path.exists(syft_folder) or not os.path.exists(syftbox_folder):
        logger.warning("syft_folder or syftbox_folder does not exist")
        return

    # Get all datasite folders in syft_folder
    syft_datasites = [f for f in os.listdir(syft_folder) if os.path.isdir(os.path.join(syft_folder, f))]

    # Check each datasite folder
    for datasite in syft_datasites:
        syft_datasite_path = os.path.join(syft_folder, datasite)
        syftbox_datasite_path = os.path.join(syftbox_folder, datasite)

        if not os.path.exists(syftbox_datasite_path):
            try:
                # Create the datasite folder in syftbox_folder
                os.makedirs(syftbox_datasite_path)
                logger.info(f"Created datasite folder in SyftBox: {syftbox_datasite_path}")

                # Copy the public key
                syft_public_key_path = os.path.join(syft_datasite_path, 'public_key.pem')
                syftbox_public_key_path = os.path.join(syftbox_datasite_path, 'public_key.pem')

                if os.path.exists(syft_public_key_path):
                    shutil.copy2(syft_public_key_path, syftbox_public_key_path)
                    logger.info(f"Copied public key for datasite: {datasite}")

                    # Create the .syftperm file
                    syftperm_path = os.path.join(syftbox_datasite_path, 'public_key.pem.syftperm')
                    perm_content = {
                        "READ": ["EVERYONE", datasite]
                    }
                    with open(syftperm_path, 'w') as perm_file:
                        json.dump(perm_content, perm_file, indent=2)
                    logger.info(f"Created .syftperm file for datasite: {datasite}")
                else:
                    logger.warning(f"Public key not found for datasite: {datasite}")

            except Exception as e:
                logger.error(f"Failed to synchronize datasite {datasite}. Error: {str(e)}")
        else:
            logger.debug(f"Datasite {datasite} already exists in SyftBox folder")

            # Check if .syftperm file exists, create if it doesn't
            syftperm_path = os.path.join(syftbox_datasite_path, 'public_key.pem.syftperm')
            if not os.path.exists(syftperm_path):
                try:
                    perm_content = {
                        "READ": ["EVERYONE", datasite]
                    }
                    with open(syftperm_path, 'w') as perm_file:
                        json.dump(perm_content, perm_file, indent=2)
                    logger.info(f"Created missing .syftperm file for existing datasite: {datasite}")
                except Exception as e:
                    logger.error(f"Failed to create .syftperm file for existing datasite {datasite}. Error: {str(e)}")

    logger.info("Datasite folder synchronization and permission file creation completed")