from pathlib import Path
from typing import Optional

import uvicorn
from typer import Option, Typer

from syftbox.server.server import app as fastapi_app

app = Typer(name="SyftBox Server", pretty_exceptions_enable=False)


# Define options separately to keep the function signature clean
is_file = dict(exists=True, file_okay=True, readable=True)
# fmt: off
PORT     = Option(5001,  "-p",  "--port",                   rich_help_panel="server", help="Local port for the SyftBox client")
WORKERS  = Option(1,     "-w",  "--workers",                rich_help_panel="server", help="Number of worker processes. Not valid with --reload")
RELOAD   = Option(False, "--reload", "--debug",             rich_help_panel="server", help="Path to SyftBox configuration file")
SSL_KEY  = Option(None,  "-k",  "--ssl-keyfile", **is_file, rich_help_panel="ssl",    help="Path to SSL key file",)
SSL_CERT = Option(None,  "-c", "--ssl-certfile", **is_file, rich_help_panel="ssl",    help="Path to SSL certificate file",)
# fmt: on


@app.callback(invoke_without_command=True)
def server(
    port: int = PORT,
    workers: int = WORKERS,
    reload: bool = RELOAD,
    ssl_key: Optional[Path] = SSL_KEY,
    ssl_cert: Optional[Path] = SSL_CERT,
):
    """Start the SyftBox server"""

    config = {
        "app": "syftbox.server.server:app" if reload else fastapi_app,
        "host": "0.0.0.0",
        "port": port,
        "log_level": "debug" if reload else "info",
        "workers": workers,
        "reload": reload,
        "ssl_keyfile": ssl_key if ssl_key else None,
        "ssl_certfile": ssl_cert if ssl_cert else None,
    }

    uvicorn.run(**config)


def main():
    app()


if __name__ == "__main__":
    main()
