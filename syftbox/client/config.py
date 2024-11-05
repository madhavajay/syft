from pathlib import Path
from typing import Optional

from rich import print as rprint
from rich.prompt import Confirm, Prompt

from syftbox.lib.lib import DEFAULT_SYNC_FOLDER, DIR_NOT_EMPTY, ClientConfig, is_valid_dir, is_valid_email


def load_config(config_path: Path) -> Optional[ClientConfig]:
    """
    Load the client configuration from the given path.
    Will not raise ClientConfigException
    """
    if not config_path or not config_path.exists():
        return None
    return ClientConfig.load(config_path)


def setup_config_interactive(config_path: Path, email: str, data_dir: Path, server: str, port: int) -> ClientConfig:
    """Setup the client configuration interactively. Called from CLI"""

    config_path = config_path.expanduser().resolve()
    data_dir = data_dir.expanduser().resolve()

    conf = load_config(config_path)

    if not conf:
        # first time setup
        if data_dir == DEFAULT_SYNC_FOLDER:
            data_dir = prompt_sync_dir()

        if not email:
            email = prompt_email()

        # create a new config with the input params
        conf = ClientConfig(
            config_path=config_path,
            sync_folder=data_dir,
            email=email,
            server_url=server,
            port=port,
        )
    else:
        # if cli args changed, then we update the config
        # not sure if we really need this
        # but keeping it or removing it both has it's pros/cons
        if email and email != conf.email:
            conf.email = email
        if data_dir and data_dir != conf.sync_folder:
            conf.sync_folder = data_dir
        if server and server != conf.server_url:
            conf.server_url = server
        if port and port != conf.port:
            conf.port = port

    conf.sync_folder.mkdir(parents=True, exist_ok=True)
    conf.save()
    return conf


def prompt_sync_dir(default_dir: Path = DEFAULT_SYNC_FOLDER) -> Path:
    while True:
        sync_folder = Prompt.ask(
            "[bold]Where do you want SyftBox to store data?[/bold] [grey70]Press Enter for default[/grey70]",
            default=str(default_dir),
        )
        valid, reason = is_valid_dir(sync_folder)
        if reason == DIR_NOT_EMPTY:
            overwrite = Confirm.ask(
                f"[bold yellow]Directory '{sync_folder}' is not empty![/bold yellow] Do you want to overwrite it?",
            )
            if not overwrite:
                continue
            valid = True

        if not valid:
            rprint(f"[bold red]{reason}[/bold red] '{sync_folder}'")
            continue

        path = Path(sync_folder).expanduser().resolve()
        rprint(f"Selected directory [bold]'{path}'[/bold]")
        return path


def prompt_email() -> str:
    while True:
        email = Prompt.ask("[bold]Enter your email address[/bold]")
        if not is_valid_email(email):
            rprint(f"[bold red]Invalid email[/bold red]: '{email}'")
            continue
        return email
