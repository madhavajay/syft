import argparse
import os
import subprocess
import sys
from collections import namedtuple

from ..lib import ClientConfig
from .app_install import install

base_path = os.path.expanduser("~/.syftbox/")
config_path = os.environ.get(
    "SYFTBOX_CLIENT_CONFIG_PATH", os.path.expanduser("~/.syftbox/client_config.json")
)


def list_app(client_config: ClientConfig) -> None:
    print("Listing apps")


def uninstall_app(client_config: ClientConfig) -> None:
    print("Uninstalling Apps")


def update_app(client_config: ClientConfig) -> None:
    print("Updating Apps")


def upgrade_app(client_config: ClientConfig) -> None:
    print("Upgrading Apps")


def main(parser, args_list) -> None:
    client_config = ClientConfig.load(config_path)

    Commands = namedtuple("Commands", ["description", "execute"])
    commands = {
        "list": Commands(
            "List all currently installed apps in your syftbox.", list_app
        ),
        "install": Commands("Install a new app in your syftbox.", install),
        "uninstall": Commands("Uninstall a certain app.", uninstall_app),
        "update": Commands("Check for app updates.", update_app),
        "upgrade": Commands("Upgrade an app.", upgrade_app),
    }

    # Add a subparser to the "app" parser to handle different actions
    app_subparsers = parser.add_subparsers(
        title="App Commands",
        dest="subcommand",
    )

    # Add all the commands to the argparser
    for command, cmd_info in commands.items():
        app_subparsers.add_parser(command, help=cmd_info.description)

    # Parse the remaining args using the parser with subparsers added
    # args = parser.parse_args(args_list)
    args, remaining_args = parser.parse_known_args()

    # Handle the subcommands as needed
    if args.subcommand:
        command = commands[args.subcommand]
        sys.argv = [sys.argv[0]] + remaining_args
        error = command.execute(client_config)
        if error is not None:
            step, exception = error
            print(f"Error during {step}: ", str(exception))
    else:
        parser.print_help()
