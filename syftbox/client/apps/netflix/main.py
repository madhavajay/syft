import argparse
import os

from imdb import run as add_imdb_data
from netflix import run as preprocess_netflix
from page import run as make_page
from tmdb import run as get_tmdb_data


def main():
    # Create the argument parser
    parser = argparse.ArgumentParser(description="Enter your TMDB API key.")

    # Add an argument for the TMDB API key
    parser.add_argument("--tmdb-api-key", required=False, help="Your TMDB API key")
    parser.add_argument(
        "--missing-imdb-file", required=False, help="Your missing IMDB title file"
    )

    # Parse the arguments
    args = parser.parse_args()

    # If the API key is not provided via args, ask for it interactively
    tmdb_api_key = args.tmdb_api_key
    if not tmdb_api_key:
        tmdb_api_key = os.environ.get("TMDB_API_KEY", None)
        if not tmdb_api_key:
            tmdb_api_key = input("Please enter your TMDB API key: ")

    print(f"Your TMDB API key is: {tmdb_api_key}")

    missing_file = None
    if args.missing_imdb_file:
        if not os.path.exists(args.missing_imdb_file):
            raise Exception(f"Can't find file: {args.missing_imdb_file}")
        print(f"> You have included a missing imdb id file: {args.missing_imdb_file}")
        missing_file = args.missing_imdb_file

    preprocess_netflix()
    get_tmdb_data(tmdb_api_key, missing_file)
    add_imdb_data()
    make_page()


if __name__ == "__main__":
    main()
