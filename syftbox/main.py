from rich import print as rprint
from typer import Typer

from syftbox import __version__
from syftbox.app.cli import app as app_cli
from syftbox.client.cli import app as client_cli
from syftbox.server.cli import app as server_cli

app = Typer(
    name="SyftBox",
    no_args_is_help=True,
    help="SyftBox CLI",
    pretty_exceptions_enable=False,
)


@app.command(rich_help_panel="General Options")
def version():
    """Print SyftBox version"""

    print(__version__)


@app.command(rich_help_panel="General Options")
def debug():
    """Print SyftBox debug data"""
    from syftbox.lib.debug import debug_report_yaml

    try:
        rprint(debug_report_yaml())
    except Exception as e:
        rprint(f"[red]Error[/red]: {e}")


app.add_typer(client_cli, name="client")
app.add_typer(server_cli, name="server")
app.add_typer(app_cli, name="app")


def main():
    app()


if __name__ == "__main__":
    main()
