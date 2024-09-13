import argparse
import sys

from syftbox.client.client import main as client_main
from syftbox.server.server import main as server_main


def main():
    parser = argparse.ArgumentParser(description="Syftbox CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Define the client command
    subparsers.add_parser("client", help="Run the Syftbox client")

    # Define the server command
    subparsers.add_parser("server", help="Run the Syftbox server")

    args, remaining_args = parser.parse_known_args()

    if args.command == "client":
        # Modify sys.argv to exclude the subcommand
        sys.argv = [sys.argv[0]] + remaining_args
        client_main()
    elif args.command == "server":
        # Modify sys.argv to exclude the subcommand
        sys.argv = [sys.argv[0]] + remaining_args
        server_main()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
