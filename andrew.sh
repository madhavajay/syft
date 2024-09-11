#!/bin/bash
cd client && uv run client.py --config_path=../users/andrew.json --sync_folder=../users/andrew --email=andrew@openmined.org --port=8082
