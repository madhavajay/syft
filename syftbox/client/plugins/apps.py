import logging
import os
import shutil

from syftbox.lib import (
    SyftPermission,
    find_and_run_script,
    get_file_hash,
    perm_file_path,
)

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = 10000
DESCRIPTION = "Runs Apps"


def run_apps(client_config):
    # create the directory
    apps_path = client_config.sync_folder + "/" + "apps"
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
            run_app(client_config, app_path)


def output_published(app_output, published_output) -> bool:
    return (
        os.path.exists(app_output)
        and os.path.exists(published_output)
        and get_file_hash(app_output) == get_file_hash(published_output)
    )


def run_app(client_config, path):
    app_name = os.path.basename(path)

    output_file = "output/index.html"
    os.makedirs(path + "/" + "output", exist_ok=True)
    output_file_path = path + "/" + output_file

    destination = "public/apps/netflix/index.html"
    destination_path = client_config.datasite_path + "/" + destination

    # extra_args = ["--force"]
    extra_args = []
    try:
        print(f"👟 Running {app_name} app", end="")
        result = find_and_run_script(path, extra_args)
        if hasattr(result, "returncode"):
            if "Already generated" not in str(result.stdout):
                print("\n")
                print(result.stdout)
            else:
                print(" - no change")
            exit_code = result.returncode
            if exit_code != 0:
                print(f"Error running: {app_name}", result.stdout, result.stderr)
    except Exception as e:
        print(f"Failed to run. {e}")

    if not output_published(output_file_path, destination_path):
        if os.path.exists(output_file_path):
            base_dir = os.path.dirname(destination_path)
            os.makedirs(base_dir, exist_ok=True)
            shutil.copy2(output_file_path, destination_path)
            print(
                f"> {app_name} published to: {client_config.server_url}/datasites/apps/netflix/{client_config.email}"
            )


def run(shared_state):
    # print("> Running Apps")
    client_config = shared_state.client_config
    run_apps(client_config)
