#!/bin/sh
uv venv .venv
uv pip install -r requirements.txt
TMDB_API_KEY=$(cat inputs/TMDB_API_KEY.txt)

uv run python -c "import syftbox; print(syftbox.__version__)"
uv run main.py --tmdb-api-key=$TMDB_API_KEY --missing-imdb-file=inputs/missing_imdb_id.json "$@"
