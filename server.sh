#!/bin/bash
uv run uvicorn syftbox.server.server:app --reload  --port 5001 --reload-dir ./syftbox
