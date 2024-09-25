import os

import pandas as pd


def run():
    try:
        temp_folder = "./temp/"
        output_file = "1_netflix.csv"

        netflix_df = pd.read_csv("./inputs/NetflixViewingHistory.csv")
        netflix_df = netflix_df.rename(
            columns={"Title": "netflix_title", "Date": "netflix_date"}
        )

        path = os.path.abspath(temp_folder + "/" + output_file)
        netflix_df.to_csv(path, index=False)
        print(f"> Writing {output_file} to {temp_folder}")

    except Exception as e:
        print("Failed to run netflix.py", e)
