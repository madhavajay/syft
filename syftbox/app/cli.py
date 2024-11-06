import sys
from pathlib import Path

from rich import print as rprint
from typer import Argument, Exit, Option, Typer
from typing_extensions import Annotated

from syftbox.app.manager import install_app, list_app, uninstall_app
from syftbox.lib.lib import DEFAULT_CONFIG_PATH, ClientConfig

app = Typer(name="SyftBox Apps", pretty_exceptions_enable=False, no_args_is_help=True, help="Manage SyftBox apps")
state = {"config": None}

CONFIG_OPTS = Option("-c", "--config", "--config-path", help="Path to the SyftBox config file")


@app.command()
def list(config_path: Annotated[Path, CONFIG_OPTS] = DEFAULT_CONFIG_PATH):
    """List all installed Syftbox apps"""
    config = load_conf(config_path)
    result = list_app(config)

    if len(result["apps"]) == 0:
        rprint(f"No apps installed in {result['apps_path']}")
        sys.exit(1)

    rprint(f"Apps installed in {result['apps_path']}:")
    for app in result["apps"]:
        rprint(f"- [bold cyan]{app}[/bold cyan]")


@app.command()
def install(
    repository: Annotated[str, Argument(..., help="Repository URL")],
    branch: Annotated[str, Option("-b", "--branch", help="Branch name")] = "main",
    config_path: Annotated[Path, CONFIG_OPTS] = DEFAULT_CONFIG_PATH,
):
    """Install a new Syftbox app"""
    config = load_conf(config_path)
    result, err = install_app(config, repository, branch)
    if err:
        rprint(f"[bold red]Error:[/bold red] {err}")
        sys.exit(1)

    rprint(f"Installed app [bold]'{result['app_name']}'[/bold]\nLocation: {result['app_dir']}")


@app.command()
def uninstall(
    app_name: Annotated[str, Argument(help="Name of the app to uninstall")],
    config_path: Annotated[Path, CONFIG_OPTS] = DEFAULT_CONFIG_PATH,
):
    """Uninstall a Syftbox app"""
    config = load_conf(config_path)
    result = uninstall_app(app_name, config)
    if not result:
        rprint(f"App not found [bold]'{app_name}'[/bold]")
        sys.exit(1)

    rprint(f"Uninstalled app [bold]'{app_name}'[/bold] from {result}")


# @app.command()
# def update(
#     app_name: Annotated[str, Argument(help="Name of the app to uninstall")],
#     config_path: Annotated[Path, CONFIG_OPTS] = DEFAULT_CONFIG_PATH,
# ):
#     """Update a Syftbox app"""
#     pass


def load_conf(config_path: Path):
    try:
        return ClientConfig.load(config_path)
    except Exception:
        msg = (
            f"[bold red]Error:[/bold red] Couldn't load config at: [yellow]{config_path}[/yellow].\n"
            "Please ensure that:\n"
            "  - The configuration file exists at the specified path.\n"
            "  - You've run the SyftBox atleast once.\n"
            f"  - For custom configs, provide the proper path using [cyan]--config[/cyan] flag"
        )
        rprint(msg)
        raise Exit(1)
