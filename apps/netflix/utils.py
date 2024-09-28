import ast
import base64
import hashlib
import json
import os
import re
import unicodedata

import requests

cache_folder = "./cache/"


def save_cache(results_cache, file_name):
    path = cache_folder + "/" + file_name
    with open(path, "w") as f:
        json.dump(results_cache, f)


def load_cache(file_name):
    path = cache_folder + "/" + file_name
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    else:
        return {}


# Function to normalize the title for search, keeping colons
def normalize_title(title):
    # Step 1: Normalize Unicode characters (decompose accents)
    title = (
        unicodedata.normalize("NFKD", title).encode("ASCII", "ignore").decode("utf-8")
    )

    # Step 2: Convert to lowercase
    title = title.lower()

    # Step 3: Remove unnecessary punctuation except for colons (keep ':')
    title = re.sub(
        r"[^\w\s:]", "", title
    )  # Keeps only letters, numbers, whitespace, and colons

    # Step 4: Strip leading/trailing whitespace
    return title.strip()


def download_file(url, folder_path, file_name=None):
    # Ensure the folder exists
    os.makedirs(folder_path, exist_ok=True)

    # Get the file name from the URL if not provided
    if file_name is None:
        file_name = url.split("/")[-1]

    # Define the full path to save the file
    file_path = os.path.join(folder_path, file_name)

    # Download the file
    response = requests.get(url, stream=True)
    response.raise_for_status()  # Check for errors

    # Write the file to the specified folder
    with open(file_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)

    print(f"File downloaded successfully and saved to: {file_path}")


def evaluate_list(value):
    try:
        # Use ast.literal_eval to safely evaluate strings into Python literals (like lists, dicts)
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        # Return the original value if it's not a valid Python literal
        return value


def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded_string}"


def compute_file_hash(filepath, hash_algorithm="sha256"):
    # Choose the hash algorithm
    hash_func = getattr(hashlib, hash_algorithm)()

    # Read file in binary mode and update hash in chunks
    with open(filepath, "rb") as file:
        while chunk := file.read(8192):
            hash_func.update(chunk)

    # Return the hex representation of the hash
    return hash_func.hexdigest()
