from pathlib import Path

import uvicorn
from rich import print as rprint
from typer import Option, Typer
from typing_extensions import Annotated

from syftbox.client.client import DEFAULT_SYNC_FOLDER, open_sync_folder
from syftbox.client.client import app as fastapi_app
from syftbox.client.utils.net import get_free_port, is_port_in_use
from syftbox.lib.lib import DEFAULT_CONFIG_PATH, DEFAULT_SERVER_URL, prompt_email, prompt_sync_dir
from syftbox.lib.logger import setup_logger

app = Typer(name="SyftBox Client", pretty_exceptions_enable=False)

# Define options separately to keep the function signature clean
# fmt: off

# ----- client commands opts -----
CLIENT_PANEL = "Client Options"
LOCAL_SERVER_PANEL = "Local Server Options"

EMAIL_OPTS = Option(
    "-e", "--email",
    rich_help_panel=CLIENT_PANEL,
    help="Email for the SyftBox datasite",
    callback=prompt_email,
)
SERVER_OPTS = Option(
    DEFAULT_SERVER_URL, "-s", "--server",
    rich_help_panel=CLIENT_PANEL,
    help="SyftBox cache server URL",
)
DATA_DIR_OPTS = Option(
    "-d", "--data-dir", "--sync_folder",
    rich_help_panel=CLIENT_PANEL,
    help="Directory where SyftBox stores data",
    callback=prompt_sync_dir,
)
CONFIG_OPTS = Option(
    DEFAULT_CONFIG_PATH, "-c", "--config", "--config_path",
    rich_help_panel=CLIENT_PANEL,
    help="Path to SyftBox configuration file",
)
OPEN_DIR_OPTS = Option(
    "--open-dir/--no-open-dir",
    rich_help_panel=CLIENT_PANEL,
    help="Will open SyftBox sync/data dir folder in file explorer",
)
PORT_OPTS = Option(
    8080, "-p", "--port",
    rich_help_panel=LOCAL_SERVER_PANEL,
    help="Local port for the SyftBox client",
)
RELOAD_OPTS = Option(
    False, "--reload", "--debug",
    rich_help_panel=LOCAL_SERVER_PANEL,
    help="Enable debug mode",
)

# ----- report command opts -----
REPORT_PATH_OPTS = Option(
    Path(".").resolve(), "-o", "-p", "--path", "--output-dir",
    help="Directory to save the log file",
)

# fmt: on


@app.callback(invoke_without_command=True)
def client(
    data_dir: Annotated[Path, DATA_DIR_OPTS] = DEFAULT_SYNC_FOLDER,
    email: Annotated[str, EMAIL_OPTS] = None,
    server: str = SERVER_OPTS,
    conf_path: Path = CONFIG_OPTS,
    port: int = PORT_OPTS,
    open_dir: Annotated[bool, OPEN_DIR_OPTS] = True,
    reload: bool = RELOAD_OPTS,
):
    """Run the SyftBox client"""

    log_level = "DEBUG" if reload else "INFO"
    setup_logger(log_level)

    # todo: untangle client config, client and fastapi server
    # prompt & validate if no config
    # generate config
    # open_sync_folder
    if open_dir:
        open_sync_folder(data_dir)

    # todo set config for fastapi app like this?
    # fastapi_app.config = dict(key="value")

    if is_port_in_use(port):
        new_port = get_free_port()
        rprint(f"[yellow]Port {port} is already in use! Switching to port {new_port}[/yellow]")
        port = new_port

    # run uvicorn
    uvicorn.run(
        # --reload/--workers requires a string path to the app
        app="syftbox.client.client:app" if reload else fastapi_app,
        host="0.0.0.0",
        port=port,
        log_level=log_level.lower(),
        reload=reload,
    )


@app.command()
def report(path: Path = REPORT_PATH_OPTS):
    """Generate a report of the SyftBox client"""
    from datetime import datetime

    from syftbox.lib.logger import zip_logs

    name = f"syftbox_logs_{datetime.now().strftime('%Y_%m_%d_%H%M')}"
    output_path = Path(path, name).resolve()
    output_path_with_extension = zip_logs(output_path)
    rprint(f"Logs saved at: {output_path_with_extension}.")


def main():
    app()


if __name__ == "__main__":
    main()
