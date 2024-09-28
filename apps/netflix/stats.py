import datetime
import json
import os

import pandas as pd
import requests
from utils import evaluate_list, image_to_base64, load_cache, save_cache

TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"  # w500 refers to image size

tmdb_id_cache = load_cache("tmdb_id.json")


def get_this_year(df, year):
    return df[df["netflix_date"].dt.year == year]


def get_imdb_id_rows(df, imdb_id):
    show_df = df[df["imdb_id"] == imdb_id]
    return show_df


def get_top_n_tv_shows(df, n):
    top_ids = df[df["tmdb_media_type"] == "tv"]["imdb_id"].value_counts().head(n).index
    return df.loc[
        df["imdb_id"].isin(top_ids) & (df["tmdb_media_type"] == "tv")
    ].drop_duplicates(subset="imdb_id", keep="first")


def format_minutes(total_minutes):
    hours = int(total_minutes // 60)
    minutes = int(total_minutes % 60)
    result = []

    if hours > 0:
        result.append(f"{hours} h{'s' if hours > 1 else ''}")
    if minutes > 0:
        result.append(f"{minutes} m{'s' if minutes > 1 else ''}")

    return ", ".join(result) if result else "0 minutes"


def get_week_counts(df):
    day_counts = df["day_of_week"].value_counts()
    favorite_days = day_counts.to_dict()
    return favorite_days


def first_day(favourite_days):
    keys = list(favourite_days.keys())
    if len(keys) > 0:
        return keys[0]
    return "Unknown"


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

    flattened_dict["tmdb_title"] = data["name"]
    poster_path = data["poster_path"]
    tmdb_poster_url = f"{IMAGE_BASE_URL}{poster_path}"
    flattened_dict["tmdb_poster_url"] = tmdb_poster_url
    return flattened_dict


def get_tmdb_details_for_tv(tmdb_id, api_key):
    media_type = "tv"
    url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}"
    params = {"api_key": api_key, "append_to_response": "external_ids"}

    cache_key = f"{tmdb_id}_{media_type}"
    if cache_key in tmdb_id_cache:
        result = tmdb_id_cache[cache_key]
        out_dict = flatten_tmdb_dict(result)
        out_dict["tmdb_id"] = tmdb_id
        return pd.Series(out_dict)

    print(f"> Querying tmdb for {cache_key}")
    response = requests.get(url, params=params)

    if response.status_code == 200:
        result = response.json()
        if result:
            tmdb_id_cache[cache_key] = result
            save_cache(tmdb_id_cache, "tmdb_id.json")
            out_dict = flatten_tmdb_dict(result)
            out_dict["tmdb_id"] = tmdb_id
            return pd.Series(out_dict)

    return None


def run(api_key):
    try:
        templates_folder = "./templates"
        output_file = "stats.html"

        stats_data = {}
        with open("./inputs/stats_data.json") as f:
            stats_data = json.loads(f.read())

        total_time = format_minutes(stats_data["total_time"])
        total_views = stats_data["total_views"]
        total_unique_show_views = stats_data["total_unique_show_views"]
        year_fav_day = stats_data["year_fav_day"]

        current_year = datetime.datetime.now().year
        top_5 = stats_data["top_5"]

        series = []
        for tmdb_id, count in top_5.items():
            series.append(get_tmdb_details_for_tv(tmdb_id, api_key))

        imdb_df = pd.DataFrame(series)

        # add imdb
        temp_folder = "./temp/"

        titles = pd.read_csv(
            temp_folder + "/title.basics.tsv.gz",
            sep="\t",
            compression="gzip",
        )

        title_ratings = pd.read_csv(
            temp_folder + "/title.ratings.tsv.gz",
            sep="\t",
            compression="gzip",
        )

        titles_merged = titles.merge(title_ratings, on="tconst", how="right")
        titles_cleaned = titles_merged.dropna()
        titles_cleaned = titles_cleaned[titles_cleaned["isAdult"] == 0]

        titles_cleaned["startYear"] = titles_cleaned["startYear"].replace("\\N", None)
        titles_cleaned["runtimeMinutes"] = titles_cleaned["runtimeMinutes"].replace(
            "\\N", None
        )

        df_merged = imdb_df.merge(
            titles_cleaned[["tconst", "runtimeMinutes", "averageRating"]],
            how="left",
            left_on="imdb_id",
            right_on="tconst",
        )

        df_merged = df_merged.rename(
            columns={
                "runtimeMinutes": "imdb_runtime_minutes",
                "averageRating": "imdb_rating",
            }
        )

        df_merged = df_merged.drop(columns=["tconst"])

        css = ""
        with open(templates_folder + "/" + "index.css") as f:
            css = f.read()

        page = ""
        with open(templates_folder + "/" + "page.html") as f:
            page = f.read()

        show_list_card_template = ""
        with open(templates_folder + "/" + "card.html") as f:
            show_list_card_template = f.read()

        show_list_html = ""
        order = 0

        for _, row in df_merged.iterrows():
            count = top_5[row.tmdb_id]
            genres = ", ".join(sorted(evaluate_list(row.genre_names)))
            order += 1
            average_rating = row.imdb_rating
            tmdb_title = row.tmdb_title
            imdb_id = row.imdb_id
            tmdb_poster_url = row.tmdb_poster_url
            template_vars = {
                "year": current_year,
                "imdb_id": imdb_id,
                "order": order,
                "tmdb_poster_url": tmdb_poster_url,
                "tmdb_title": tmdb_title,
                "average_rating": average_rating,
                "genres": genres,
                "count": count,
                "fav_day": "",
            }
            show_list_html += show_list_card_template.format(**template_vars)

        logo_path = "templates/images/nf_logo.png"
        logo_src = image_to_base64(logo_path)

        page_vars = {
            "logo_src": logo_src,
            "css": css,
            "year": current_year,
            "total_time": total_time,
            "year_fav_day": year_fav_day,
            "total_unique_show_views": total_unique_show_views,
            "total_views": total_views,
            "show_list_html": show_list_html,
        }
        page_html = page.format(**page_vars)

        print(f"Writing {output_file} to output")
        path = "output" + "/" + output_file
        with open(path, "w") as f:
            f.write(page_html)
        full_path = os.path.abspath(path)
        print(f"\nOpen: file:///{full_path}")

    except Exception as e:
        import traceback

        print(traceback.print_exc())
        print("Failed to run html.py", e)


api_key = "010de1bcf60f0e14b92765a3f9485662"
run(api_key)
