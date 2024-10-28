import json
import os
import secrets
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, field_validator
from typing_extensions import Self

from syftbox.lib.types import PathLike, to_path

__all__ = ["SyftClientConfig", "DEFAULT_SERVER_URL", "DEFAULT_DATA_DIR", "DEFAULT_CONFIG_PATH"]

DEFAULT_SERVER_URL = "https://syftbox.openmined.org"
DEFAULT_DATA_DIR = Path(Path.home(), "syftbox-data")
DEFAULT_PORT = 38080
LEGACY_CONIFG_PATH = Path(Path.home(), ".syftbox", "client_config.json")
STATIC_CONFIG_PATH = Path(Path.home(), ".syftbox", "config.json")

DEFAULT_CONFIG_PATH = os.getenv("SYFTBOX_CLIENT_CONFIG", STATIC_CONFIG_PATH)


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

    def save(self):
        self.path.write_text(self.as_json())

    def as_json(self, indent=4):
        return self.model_dump_json(indent=4, exclude_none=True, warnings="none")

    @classmethod
    def load(cls, path: PathLike) -> Self:
        path = to_path(path)
        data = json.loads(path.read_text())
        return cls(path=path, **data)

    @classmethod
    def exists(cls, path: PathLike) -> bool:
        return to_path(path).exists()


if __name__ == "__main__":
    conf = SyftClientConfig.load()
    conf.token = secrets.token_hex(32)
    print(conf)
    conf.save()
