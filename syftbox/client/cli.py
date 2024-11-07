from pathlib import Path

from rich import print as rprint
from typer import Context, Option, Typer
from typing_extensions import Annotated

from syftbox.client.client import run_client
from syftbox.client.config import setup_config_interactive
from syftbox.client.utils.net import get_free_port, is_port_in_use
from syftbox.lib.lib import DEFAULT_CONFIG_PATH, DEFAULT_SERVER_URL, DEFAULT_SYNC_FOLDER

app = Typer(
    name="SyftBox Client",
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Define options separately to keep the function signature clean
# fmt: off

# client commands opts
CLIENT_PANEL = "Client Options"
LOCAL_SERVER_PANEL = "Local Server Options"

EMAIL_OPTS = Option(
    "-e", "--email",
    rich_help_panel=CLIENT_PANEL,
    help="Email for the SyftBox datasite",
)
SERVER_OPTS = Option(
    "-s", "--server",
    rich_help_panel=CLIENT_PANEL,
    help="SyftBox cache server URL",
)
DATA_DIR_OPTS = Option(
    "-d", "--data-dir", "--sync_folder",
    rich_help_panel=CLIENT_PANEL,
    help="Directory where SyftBox stores data",
)
CONFIG_OPTS = Option(
    "-c", "--config", "--config_path",
    rich_help_panel=CLIENT_PANEL,
    help="Path to SyftBox configuration file",
)
OPEN_OPTS = Option(
    is_flag=True,
    rich_help_panel=CLIENT_PANEL,
    help="Open SyftBox sync/data dir folder on client start",
)
PORT_OPTS = Option(
    "-p", "--port",
    rich_help_panel=LOCAL_SERVER_PANEL,
    help="Local port for the SyftBox client",
)
RELOAD_OPTS = Option(
    rich_help_panel=LOCAL_SERVER_PANEL,
    help="Run server in hot reload. Should not see this in production",
)
VERBOSE_OPTS = Option(
    "-v", "--verbose",
    is_flag=True,
    help="Enable verbose mode",
)

# report command opts
REPORT_PATH_OPTS = Option(
    Path(".").resolve(), "-o", "-p", "--path", "--output-dir",
    help="Directory to save the log file",
)

# fmt: on


@app.callback(invoke_without_command=True)
def client(
    ctx: Context,
    data_dir: Annotated[Path, DATA_DIR_OPTS] = DEFAULT_SYNC_FOLDER,
    email: Annotated[str, EMAIL_OPTS] = None,
    server: Annotated[str, SERVER_OPTS] = DEFAULT_SERVER_URL,
    config_path: Annotated[Path, CONFIG_OPTS] = DEFAULT_CONFIG_PATH,
    port: Annotated[int, PORT_OPTS] = 8080,
    open_dir: Annotated[bool, OPEN_OPTS] = True,
    verbose: Annotated[bool, VERBOSE_OPTS] = False,
):
    """Run the SyftBox client"""

    if ctx.invoked_subcommand is not None:
        # If a subcommand is being invoked, just return
        return

    if port == 0:
        port = get_free_port()
        rprint(f"[yellow]Allocated port {port}[yellow]")
    elif is_port_in_use(port):
        new_port = get_free_port()
        rprint(f"[yellow]Port {port} is already in use! Switching to port {new_port}[/yellow]")
        port = new_port

    client_config = setup_config_interactive(config_path, email, data_dir, server, port)
    run_client(client_config=client_config, open_dir=open_dir, verbose=verbose)


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
