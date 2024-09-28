import datetime
import os

import pandas as pd
from utils import evaluate_list, image_to_base64


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


def run():
    try:
        templates_folder = "./templates"
        output_file = "index.html"

        imdb_df = pd.read_csv("./temp/3_imdb.csv")
        imdb_df["netflix_date"] = pd.to_datetime(imdb_df["netflix_date"])
        imdb_df["day_of_week"] = imdb_df["netflix_date"].dt.day_name()
        imdb_df["genre_names"] = imdb_df["genre_names"].apply(evaluate_list)
        imdb_df["genre_ids"] = imdb_df["genre_ids"].apply(evaluate_list)

        current_year = datetime.datetime.now().year
        year_df = get_this_year(imdb_df, current_year)
        year_tv_df = year_df[year_df["tmdb_media_type"] == "tv"]

        # year stats
        total_time = format_minutes(year_tv_df["imdb_runtime_minutes"].sum())
        year_fav_day = first_day(get_week_counts(year_tv_df))
        total_unique_show_views = year_tv_df["imdb_id"].nunique()
        total_views = len(year_tv_df)

        top_5_shows = get_top_n_tv_shows(year_df, 5)

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
        for _, row in top_5_shows.iterrows():
            show_rows = get_imdb_id_rows(year_tv_df, row.imdb_id)
            genres = ", ".join(sorted(row.genre_names))
            order += 1
            # fav_days = get_week_counts_for_imdbid(df, row.imdbID)
            fav_day = first_day(get_week_counts(show_rows))
            count = len(show_rows)
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
                "fav_day": fav_day,
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
        print("Failed to run page.py", e)


if __name__ == "__main__":
    run()
