import json
import os
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, field_validator
from rich import print as rprint
from rich.prompt import Confirm, Prompt
from typing_extensions import Self

from syftbox.lib.lib import DEFAULT_SYNC_FOLDER, DIR_NOT_EMPTY, ClientConfig, is_valid_dir, is_valid_email
from syftbox.lib.types import PathLike, to_path


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


__all__ = ["SyftClientConfig", "DEFAULT_SERVER_URL", "DEFAULT_DATA_DIR", "DEFAULT_CONFIG_PATH"]

DEFAULT_SERVER_URL = "https://syftbox.openmined.org"
DEFAULT_PORT = 38080
DEFAULT_DATA_DIR = Path(Path.home(), "syftbox-data")
LEGACY_CONFIG_PATH = Path(Path.home(), ".syftbox", "client_config.json")
CLIENT_CONFIG_PATH = Path(Path.home(), ".syftbox", "config.json")

# env or default
DEFAULT_CONFIG_PATH = os.getenv("SYFTBOX_CLIENT_CONFIG_PATH", CLIENT_CONFIG_PATH)


class Config(BaseModel):
    """Client configuration that gets serialized to JSON on disk."""

    # model config
    model_config = ConfigDict(extra="ignore")

    data_dir: Path = Field(
        validation_alias=AliasChoices("data_dir", "sync_folder"),
        default=DEFAULT_DATA_DIR,
    )
    """Local directory where client data is stored"""

    server_url: AnyHttpUrl = Field(
        default=DEFAULT_SERVER_URL,
        description="",
    )
    """URL of the remote SyftBox server"""

    client_url: AnyHttpUrl = Field(
        validation_alias=AliasChoices("client_url", "port"),
        description="",
    )
    """URL where the client is running"""

    email: EmailStr
    """Email address of the user"""

    token: Optional[str] = Field(default=None)
    """API token for the user"""

    @field_validator("client_url", mode="before")
    def port_to_url(cls, val):
        if isinstance(val, int):
            return f"http://localhost:{val}"
        return val

    @field_validator("token", mode="before")
    def token_to_str(cls, v):
        if not v:
            return None
        elif isinstance(v, int):
            return str(v)
        return v


class SyftClientConfig(Config):
    # exclude this from getting serialized
    # but maintain it in the model for internal use
    path: Path = Field(exclude=True)
    """Path to the config file"""

    def as_json(self, indent=4):
        return self.model_dump_json(indent=4, exclude_none=True, warnings="none")

    def save(self):
        self.path.write_text(self.as_json())

    @classmethod
    def load(cls, conf_path: Optional[PathLike] = None) -> Self:
        """Load configuration from a path.

        If conf_path is not provided, it will look for the config file in the following order:
        - `SYFTBOX_CLIENT_CONFIG_PATH` environment variable
        - `~/.syftbox/config.json`
        """

        # args or env or default
        path = conf_path or DEFAULT_CONFIG_PATH
        path = to_path(path)
        data = json.loads(path.read_text())
        return cls(path=path, **data)

    @classmethod
    def exists(cls, path: PathLike) -> bool:
        return to_path(path).exists()

    @classmethod
    def migrate(cls):
        # move the legacy config to the new path
        # call this before load()
        if LEGACY_CONFIG_PATH.exists():
            LEGACY_CONFIG_PATH.rename(CLIENT_CONFIG_PATH)


if __name__ == "__main__":
    SyftClientConfig.migrate()
    conf = SyftClientConfig.load()
    print(conf)
    conf.save()
