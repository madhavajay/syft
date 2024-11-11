#!/bin/sh

set -e

if [ ! -d .venv ]; then
    uv venv
fi
uv pip install --upgrade syftbox
. .venv/bin/activate
python main.py
deactivate
