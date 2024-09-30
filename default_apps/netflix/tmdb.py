import datetime
import json
import math
import os

import pandas as pd
import requests
from utils import load_cache, normalize_title, save_cache

TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"  # w500 refers to image size

tmdb_id_cache = load_cache("tmdb_id.json")
tmdb_search_cache = load_cache("tmdb_search.json")
imdb_tmdb_cache = load_cache("imdb_tmdb.json")


def add_to_missing(one_or_many, tmdb_id, missing_imdb_id):
    if not isinstance(one_or_many, list):
        one_or_many = [one_or_many]
    for one in one_or_many:
        missing_imdb_id[one] = tmdb_id
    save_cache(missing_imdb_id, "missing_imdb_id.json")


def in_manual_mapping(original_title, missing_imdb_id):
    titles = []
    titles.append(original_title.lower())
    titles.append(normalize_title(original_title).lower())
    lower_keys = {k.lower(): v for k, v in missing_imdb_id.items()}
    for title in titles:
        for key, value in lower_keys.items():
            if title in key or key in title:
                return value
    return None


def search_tmdb_title(title, api_key, missing_imdb_id):
    url = f"{TMDB_BASE_URL}/search/multi"
    params = {"api_key": api_key, "query": title}
    if title in tmdb_search_cache:
        result = tmdb_search_cache[title]
        return pd.Series(result)

    data = None

    # check manual mapping where a user can set the imdb tconst id by hand
    manual_tmdb_id = in_manual_mapping(title, missing_imdb_id)
    if manual_tmdb_id:
        print(
            f"> Resolving {title} imdb_id: {manual_tmdb_id} from supplied missing file"
        )
        data = get_tmdb_details_by_imdb_id(manual_tmdb_id, api_key)
        tmdb_search_cache[title] = data
        save_cache(tmdb_search_cache, "tmdb_search.json")
        return pd.Series(data)

    if data is None:
        print(f"> Searching tmdb for {title}")
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if "results" in data:
                for result in data["results"]:
                    if result["media_type"] in ["tv", "movie"]:
                        tmdb_search_cache[title] = result
                        save_cache(tmdb_search_cache, "tmdb_search.json")
                        return pd.Series(result)

    return None


def flatten_tmdb_dict(data):
    flattened_dict = {}
    flattened_dict["homepage"] = data.get("homepage", None)
    external_ids = data.get("external_ids", {})
    flattened_dict["imdb_id"] = external_ids.get("imdb_id", None)
    flattened_dict["facebook_id"] = external_ids.get("facebook_id", None)
    flattened_dict["instagram_id"] = external_ids.get("instagram_id", None)
    flattened_dict["twitter_id"] = external_ids.get("twitter_id", None)
    genres = data.get("genres", {})
    genre_ids = []
    genre_names = []
    for genre in genres:
        genre_ids.append(genre["id"])
        genre_names.append(genre["name"])
    flattened_dict["genre_ids"] = genre_ids
    flattened_dict["genre_names"] = genre_names
    return flattened_dict


def get_tmdb_id_field(row) -> int | None:
    try:
        if "tmdb_id" in row:
            return int(row["tmdb_id"])
    except Exception:
        pass
    return None


def get_tmdb_media_type_field(row) -> int | None:
    try:
        if "tmdb_media_type" in row:
            math.isnan(row["tmdb_media_type"])
    except Exception:
        if isinstance(row["tmdb_media_type"], str):
            return row["tmdb_media_type"]
        pass
    return None


def get_tmdb_details(row, api_key):
    tmdb_id = get_tmdb_id_field(row)
    media_type = get_tmdb_media_type_field(row)

    if not isinstance(tmdb_id, int) or not isinstance(media_type, str):
        print(f"> Skipping {row.netflix_title} no tmdb_id")
        return None
    url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}"
    params = {"api_key": api_key, "append_to_response": "external_ids"}

    cache_key = f"{tmdb_id}_{media_type}"
    if cache_key in tmdb_id_cache:
        result = tmdb_id_cache[cache_key]
        return pd.Series(flatten_tmdb_dict(result))

    print(f"> Querying tmdb for {cache_key}")
    response = requests.get(url, params=params)

    if response.status_code == 200:
        result = response.json()
        if result:
            tmdb_id_cache[cache_key] = result
            save_cache(tmdb_id_cache, "tmdb_id.json")
            return pd.Series(flatten_tmdb_dict(result))

    return None


def get_tmdb_details_by_imdb_id(imdb_id, api_key):
    if imdb_id in imdb_tmdb_cache:
        print(f"Getting imdb_id: {imdb_id} from cache")
        return imdb_tmdb_cache[imdb_id]

    url = f"https://api.themoviedb.org/3/find/{imdb_id}"
    params = {"api_key": api_key, "external_source": "imdb_id"}

    print(f"> Querying tmdb for imdb_id: {imdb_id}")
    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        sections = [
            "movie_results",
            "person_results",
            "tv_results",
            "tv_episode_results",
            "tv_season_results",
        ]

        data_dict = None
        for section in sections:
            if data.get(section):
                # Get the first result in the section
                data_dict = data[section][0]
                imdb_tmdb_cache[imdb_id] = data_dict
                save_cache(imdb_tmdb_cache, "imdb_tmdb.json")
                return data_dict


def get_tmdb_id(row, tmdb_api_key, missing_imdb_id):
    original_title = row["netflix_title"]
    title = normalize_title(original_title)

    # Check for season/episode/series/volume in the title
    if any(
        keyword in title.lower()
        for keyword in ["season", "episode", "series", "volume", " part"]
    ):
        # Split by colon and take the first part
        title = title.split(":")[0].strip()

    result = search_tmdb_title(title, tmdb_api_key, missing_imdb_id)
    if result is None:
        title = title.split(":")[0].strip()
        # if splitting it changes it lets try again anyway
        if title != normalize_title(original_title):
            result = search_tmdb_title(title, tmdb_api_key, missing_imdb_id)
            if result is not None:
                # make sure repeated search gets cached at first title as well
                tmdb_search_cache[normalize_title(original_title)] = result.to_dict()
                save_cache(tmdb_search_cache, "tmdb_search.json")

    if result is not None:
        # shows have names and movies have titles
        df = pd.DataFrame([result])
        if "name" in df.columns:
            title_name = "name"
        elif "title" in df.columns:
            title_name = "title"
        else:
            raise Exception(f"Title is missing {row}")

        poster_path = result.get("poster_path")
        tmdb_poster_url = f"{IMAGE_BASE_URL}{poster_path}"
        df["tmdb_poster_url"] = tmdb_poster_url

        df = df.rename(
            columns={
                title_name: "tmdb_title",
                "id": "tmdb_id",
                "media_type": "tmdb_media_type",
            }
        )

        keep_cols = ["tmdb_id", "tmdb_title", "tmdb_media_type", "tmdb_poster_url"]
        df = df[keep_cols]
        return pd.Series(df.iloc[0])

    return None


def get_this_year(df, year):
    return df[df["netflix_date"].dt.year == year]


def run(api_key, missing_file):
    try:
        missing_imdb_id = {}
        temp_folder = "./temp/"
        output_file = "2_tmdb.csv"

        if missing_file is not None:
            missing_file_path = os.path.abspath(missing_file)
            if os.path.exists(missing_file_path):
                try:
                    with open(missing_file_path, "r") as f:
                        missing_imdb_id = json.load(f)
                except Exception as e:
                    print(f"Failed to load file: {missing_file_path}. {e}")

        tmdb_df = pd.read_csv("./temp/1_netflix.csv")

        tmdb_df["netflix_date"] = pd.to_datetime(
            tmdb_df["netflix_date"], format=r"%m/%d/%y"
        )

        current_year = datetime.datetime.now().year
        tmdb_df = get_this_year(tmdb_df, current_year)

        sample_tmdb_id = tmdb_df.apply(
            lambda row: pd.concat([row, get_tmdb_id(row, api_key, missing_imdb_id)]),
            axis=1,
        )

        df = sample_tmdb_id.apply(
            lambda row: pd.concat(
                [
                    row,
                    get_tmdb_details(row, api_key),
                ]
            ),
            axis=1,
        )

        # split and save missing imdb_id records
        column_name = "imdb_id"
        df_missing = df[df[column_name].isna()]
        if len(df_missing) > 0:
            missing_path = temp_folder + "/" + "2_missing.csv"
            print(f"> You have {len(df_missing)} missing rows see: {missing_path}")
            helper = r"""
To fix your missing imdb IDs you can create a manual json file.

Run:
echo '{"Life: Primates": "tt1533395"}' > my-missing-ids.json
python main.py --missing-imdb-file=my-missing-ids.json

Note: The titles can be partial string matches.
"""
            print(helper)
            df_missing.to_csv(missing_path, index=False)

        df_imdb_id = df[df[column_name].notna()]

        path = os.path.abspath(temp_folder + "/" + output_file)
        df_imdb_id.to_csv(path, index=False)
        print(f"> Writing {output_file} to {temp_folder}")

    except Exception as e:
        import traceback

        print(traceback.print_exc())
        print("Failed to run tmdb.py", e)
