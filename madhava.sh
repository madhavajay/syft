#!/bin/bash
cd client && uv run client.py --config_path=../users/madhava.json --sync_folder=../users/madhava --email=madhava@openmined.org --port=8081
