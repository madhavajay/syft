import os
import warnings

import pandas as pd
from utils import download_file

# Suppress only DtypeWarning
warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)


download_urls = [
    "https://datasets.imdbws.com/title.basics.tsv.gz",
    "https://datasets.imdbws.com/title.ratings.tsv.gz",
]


def run():
    try:
        temp_folder = "./temp/"
        output_file = "3_imdb.csv"

        imdb_df = pd.read_csv("./temp/2_tmdb.csv")

        for download_url in download_urls:
            filename = os.path.basename(download_url)
            file_path = f"{temp_folder}/{filename}"
            if not os.path.exists(file_path):
                print(f"> Downloading {download_url} to {file_path}")
                download_file(download_url, temp_folder)
            else:
                # print(f"> File {file_path} already downloaded")
                pass

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

        path = os.path.abspath(temp_folder + "/" + output_file)
        print(f"Writing {output_file} to {temp_folder}")
        df_merged.to_csv(path, index=False)

    except Exception as e:
        import traceback

        print(traceback.print_exc())
        print("Failed to run imdb.py", e)


if __name__ == "__main__":
    run()
