import argparse
import os

from imdb import run as add_imdb_data
from netflix import run as preprocess_netflix
from page import run as make_page
from tmdb import run as get_tmdb_data
from utils import compute_file_hash, load_cache, save_cache


def main():
    # Create the argument parser
    parser = argparse.ArgumentParser(description="Enter your TMDB API key.")

    # Add an argument for the TMDB API key
    parser.add_argument("--tmdb-api-key", required=False, help="Your TMDB API key")
    parser.add_argument(
        "--missing-imdb-file", required=False, help="Your missing IMDB title file"
    )
    parser.add_argument(
        "--force", action="store_true", default=False, help="Override hash check"
    )

    os.makedirs("./cache", exist_ok=True)
    os.makedirs("./inputs", exist_ok=True)
    os.makedirs("./temp", exist_ok=True)
    os.makedirs("./output", exist_ok=True)

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
            print(f"Can't find missing imdb id file at: {args.missing_imdb_file}")
        missing_file = args.missing_imdb_file

    input_file = "./inputs/NetflixViewingHistory.csv"
    if not os.path.exists(input_file):
        print(f"Netflix file: {input_file} required.")
        return
    file_hash = compute_file_hash(input_file)
    last_run = load_cache("last_run.json")
    if (
        "input_hash" in last_run
        and last_run["input_hash"] == file_hash
        and not args.force
    ):
        print(f"Already generated html for {input_file} with hash: {file_hash}")
        return

    preprocess_netflix()
    get_tmdb_data(tmdb_api_key, missing_file)
    add_imdb_data()
    make_page()

    last_run["input_hash"] = file_hash
    save_cache(last_run, "last_run.json")


if __name__ == "__main__":
    main()
