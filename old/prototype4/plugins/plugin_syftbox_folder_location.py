import rumps
import logging
import os

def execute(data, shared_state):
    def prompt_callback(key):
        try:
            prompt_message = "Please select the SyftBox folder location:"
            response = rumps.Window(
                title="SyftBox Folder Location",
                message=prompt_message,
                default_text="",
                dimensions=(320, 160)
            ).run()
            return response.text if response.text else ""
        except Exception as e:
            logging.error(f"Error in SyftBox folder location plugin prompt: {e}")
            return ""

    def run():
        try:
            folder_location = shared_state.request_config(
                'folder_location', 
                prompt_callback, 
                namespace='syftbox_folder_location'
            )
            if os.path.isdir(folder_location):
                message = f"SyftBox folder location set to: {folder_location}"
            else:
                message = f"Invalid folder location: {folder_location}"
            logging.info(message)
            rumps.notification(title="SyftBox Folder Location", subtitle="", message=message)
        except Exception as e:
            logging.error(f"Error in SyftBox folder location plugin execution: {e}")

    return run