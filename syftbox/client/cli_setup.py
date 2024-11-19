"""
SyftBox CLI - Setup scripts
"""

import json
import shutil
from pathlib import Path

import httpx
import typer
from rich import print as rprint
from rich.prompt import Confirm, Prompt

from syftbox.__version__ import __version__
from syftbox.client.client2 import METADATA_FILENAME
from syftbox.lib.client_config import SyftClientConfig
from syftbox.lib.constants import DEFAULT_DATA_DIR
from syftbox.lib.exceptions import ClientConfigException
from syftbox.lib.validators import DIR_NOT_EMPTY, is_valid_dir, is_valid_email

__all__ = ["setup_config_interactive"]


def has_old_syftbox_version(data_dir: Path) -> bool:
    """True if the data_dir was created with an older version of SyftBox"""
    metadata_file = data_dir / METADATA_FILENAME
    if not metadata_file.exists():
        return True
    metadata = json.loads(metadata_file.read_text())
    current_version = __version__
    old_version = metadata.get("version", None)
    return old_version != current_version


def prompt_delete_old_data_dir(data_dir: Path) -> bool:
    msg = f"[yellow]Found old SyftBox folder at {data_dir}.[/yellow]\n"
    msg += "[yellow]Press Y to remove the old folder and download it from the server [bold](recommended)[/bold]. Press N to keep the old folder and migrate it.[/yellow]"
    return Confirm.ask(msg)


def get_migration_decision(data_dir: Path):
    migrate_datasite = False
    if data_dir.exists():
        if has_old_syftbox_version(data_dir):
            # we need this extra if because we do 2 things:
            # 1. determine if we want to remove
            # 2. determine if we want to migrate
            if prompt_delete_old_data_dir(data_dir):
                rprint("Removing old syftbox folder")
                shutil.rmtree(str(data_dir))
                migrate_datasite = False
            else:
                migrate_datasite = True
    return migrate_datasite


def setup_config_interactive(
    config_path: Path, email: str, data_dir: Path, server: str, port: int, skip_auth: bool = False
) -> SyftClientConfig:
    """Setup the client configuration interactively. Called from CLI"""

    config_path = config_path.expanduser().resolve()
    conf: SyftClientConfig = None
    if data_dir:
        data_dir = data_dir.expanduser().resolve()

    # try to load the existing config
    try:
        conf = SyftClientConfig.load(config_path)
    except ClientConfigException:
        pass

    if not conf:
        # first time setup
        if not data_dir or data_dir == DEFAULT_DATA_DIR:
            data_dir = prompt_data_dir()

        if not email:
            email = prompt_email()

        # create a new config with the input params
        conf = SyftClientConfig(
            path=config_path,
            sync_folder=data_dir,
            email=email,
            server_url=server,
            port=port,
        )
    else:
        if server and server != conf.server_url:
            conf.set_server_url(server)
        if port != conf.client_url.port:
            conf.set_port(port)

    if conf.access_token is None and not skip_auth:
        conf.access_token = authenicate_user(conf)

    # DO NOT SAVE THE CONFIG HERE.
    # We don't know if the client will accept the config yet
    return conf


def validate_email_token(auth_client: httpx.Client) -> str:
    is_valid = False
    while not is_valid:
        email_token = Prompt.ask(
            "[yellow]Please enter the token sent to your email. Also check your spam folder[/yellow]"
        )

        response = auth_client.post(
            "/auth/validate_email_token",
            headers={"Authorization": f"Bearer {email_token}"},
        )

        if response.status_code == 200:
            is_valid = True
            access_token = response.json()["access_token"]
        elif response.status_code == 401:
            rprint("[red]Invalid token, please copy the full token from your email[/red]")
        else:
            rprint(f"[red]An unexpected error occurred: {response.text}[/red]")
            typer.Exit(1)
    return access_token


def authenicate_user(conf: SyftClientConfig) -> str:
    auth_client = httpx.Client(base_url=conf.server_url)
    response = auth_client.post(
        "/auth/request_email_token",
        json={"email": conf.email},
    )
    response.raise_for_status()

    # if email_token is there, auth is disabled and we get the email_token directly
    email_token = response.json().get("email_token", None)
    if email_token:
        rprint("[yellow]You are in [bold]development mode[/bold]. No email validation required.[/yellow]")
    else:
        access_token = validate_email_token(auth_client)

    response.raise_for_status()
    access_token = response.json()["access_token"]
    return access_token


def prompt_data_dir(default_dir: Path = DEFAULT_DATA_DIR) -> Path:
    prompt_dir = "[bold]Where do you want SyftBox to store data?[/bold] [grey70]Press Enter for default[/grey70]"
    prompt_overwrite = "[bold yellow]Directory '{sync_folder}' is not empty![/bold yellow] Do you want to overwrite it?"

    while True:
        sync_folder = Prompt.ask(prompt_dir, default=str(default_dir))
        valid, reason = is_valid_dir(sync_folder)
        if reason == DIR_NOT_EMPTY:
            overwrite = Confirm.ask(prompt_overwrite.format(sync_folder=sync_folder))
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
