#!/bin/bash
export SYFTBOX_DEV="true"
uv run syftbox/client/client.py --config_path=./users/me.json --sync_folder=./users/me --email=me@madhavajay.com --port=8085 --server=http://localhost:5001
