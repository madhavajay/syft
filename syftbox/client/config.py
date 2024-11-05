from pathlib import Path
from typing import Optional

from syftbox.lib.lib import DEFAULT_SYNC_FOLDER, ClientConfig, is_valid_dir, is_valid_email


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

    conf = load_config(config_path)

    if not conf:
        # first time setup
        if not email:
            email = prompt_email()

        if data_dir.expanduser().resolve() == DEFAULT_SYNC_FOLDER:
            data_dir = prompt_sync_dir()

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

    conf.save()
    return conf


def get_user_input(prompt, default: Optional[str] = None):
    """Get user input from the command line"""

    if default:
        prompt = f"{prompt} (default: {default}): "

    user_input = input(prompt).strip()

    return user_input or default


def prompt_sync_dir(default_dir: Path = DEFAULT_SYNC_FOLDER) -> Path:
    while True:
        sync_folder = get_user_input(
            "Where do you want to Sync SyftBox to? Press Enter for default",
            default_dir,
        )
        valid, reason = is_valid_dir(sync_folder)
        if not valid:
            print(f"Invalid directory: '{sync_folder}'. {reason}")
            continue
        return Path(sync_folder).expanduser().resolve()


def prompt_email() -> str:
    while True:
        email = get_user_input("Enter your email address: ")
        if not is_valid_email(email):
            print(f"Invalid email: '{email}'")
            continue
        return email
