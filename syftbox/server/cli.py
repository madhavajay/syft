from pathlib import Path
from typing import Optional

import uvicorn
from typer import Option, Typer

from syftbox.server.server import app as fastapi_app

app = Typer(name="SyftBox Server", pretty_exceptions_enable=False)


# Define options separately to keep the function signature clean
# fmt: off
is_file = dict(exists=True, file_okay=True, readable=True)
SERVER_PANEL = "Server Options"
SSL_PANEL = "SSL Options"

PORT_OPTS = Option(
    5001, "-p", "--port",
    rich_help_panel=SERVER_PANEL,
    help="Local port for the SyftBox client",
)
WORKERS_OPTS = Option(
    1, "-w", "--workers",
    rich_help_panel=SERVER_PANEL,
    help="Number of worker processes. Not valid with --debug/--reload",
)
RELOAD_OPTS = Option(
    False, "--reload", "--debug",
    rich_help_panel=SERVER_PANEL,
    help="Enable debug mode",
)
SSL_KEY_OPTS = Option(
    None, "--key", "--ssl-keyfile",
    **is_file,
    rich_help_panel=SSL_PANEL,
    help="Path to SSL key file",
)
SSL_CERT_OPTS = Option(
    None, "--cert", "--ssl-certfile",
    **is_file,
    rich_help_panel=SSL_PANEL,
    help="Path to SSL certificate file",
)
# fmt: on


@app.callback(invoke_without_command=True)
def server(
    port: int = PORT_OPTS,
    workers: int = WORKERS_OPTS,
    reload: bool = RELOAD_OPTS,
    ssl_key: Optional[Path] = SSL_KEY_OPTS,
    ssl_cert: Optional[Path] = SSL_CERT_OPTS,
):
    """Start the SyftBox server"""

    config = {
        "app": "syftbox.server.server:app" if (reload or workers > 1) else fastapi_app,
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
