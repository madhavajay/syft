from pathlib import Path
from typing import Optional

from rich import print as rprint
from typer import Option, Typer

from syftbox.client.client import DEFAULT_SYNC_FOLDER
from syftbox.lib.lib import DEFAULT_CONFIG_PATH, DEFAULT_SERVER_URL

app = Typer(name="SyftBox Client", pretty_exceptions_enable=False)

# Define options separately to keep the function signature clean
# fmt: off
EMAIL    = Option(None,                "-e", "--email",                     help="Email for the SyftBox datasite")
SERVER   = Option(DEFAULT_SERVER_URL,  "-s", "--server",                    help="SyftBox cache server URL")
DATA_DIR = Option(DEFAULT_SYNC_FOLDER, "-d", "--data-dir", "--sync_folder", help="Directory where SyftBox stores data")
CONFIG   = Option(DEFAULT_CONFIG_PATH, "-c", "--config",   "--config_path", help="Path to SyftBox configuration file")
PORT     = Option(8080,                "-p", "--port",                      help="Local port for the SyftBox client")
DEBUG    = Option(False,               "--debug",                           help="Enable debug mode")
NO_OPEN  = Option(False,               "--no-open-dir",                     help="Do not open the SyftBox sync folder")
# fmt: on


@app.callback(invoke_without_command=True)
def client(
    email: Optional[str] = EMAIL,
    server: str = SERVER,
    data_dir: Path = DATA_DIR,
    conf_path: Path = CONFIG,
    port: int = PORT,
    debug: bool = DEBUG,
    no_open_dir: bool = NO_OPEN,
):
    """Run the SyftBox client"""

    # todo: untangle client config, client and fastapi server
    raise NotImplementedError()


@app.command()
def report(
    path: Path = Option(".", "-o", "-p", "--path", "--output-dir", help="Directory to save the log file"),
):
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
