import logging
import os
import shutil

from syftbox.lib import SyftPermission, find_and_run_script, perm_file_path

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = 2000
DESCRIPTION = "Runs Apps"


def run_apps(client_config):
    # create the directory
    apps_path = client_config.datasite_path + "/" + "apps"
    os.makedirs(apps_path, exist_ok=True)

    # add the first perm file
    file_path = perm_file_path(apps_path)
    if os.path.exists(file_path):
        perm_file = SyftPermission.load(file_path)
    else:
        print(f"> {client_config.email} Creating Apps Permfile")
        try:
            perm_file = SyftPermission.datasite_default(client_config.email)
            perm_file.save(file_path)
        except Exception as e:
            print("Failed to create perm file", e)

    apps = os.listdir(apps_path)
    for app in apps:
        app_path = os.path.abspath(apps_path + "/" + app)
        if os.path.isdir(app_path):
            print("got app", app)
            run_app(client_config, app_path)


def run_app(client_config, path):
    app_name = os.path.basename(path)
    print(f"> Running {app_name } app")

    # extra_args = ["--force"]
    extra_args = []
    try:
        result = find_and_run_script(path, extra_args)
        if hasattr(result, "returncode"):
            print(result.stdout)
            exit_code = result.returncode
            if exit_code != 0:
                print(f"Error running: {app_name}", result.stdout, result.stderr)
    except Exception as e:
        print(f"Failed to run. {e}")

    output_file = "output/index.html"
    output_file_path = path + "/" + output_file
    print("output_file_path", output_file_path)
    if os.path.exists(output_file_path):
        destination = "public/index.html"
        destination_path = client_config.datasite_path + "/" + destination
        base_dir = os.path.dirname(destination_path)
        os.makedirs(base_dir, exist_ok=True)
        shutil.copy2(output_file_path, destination_path)
        print(
            f"{app_name} Published to: {client_config.server_url}/dataites/{client_config.datasite}"
        )


def run(shared_state):
    # print("> Running Apps")
    client_config = shared_state.client_config
    run_apps(client_config)
