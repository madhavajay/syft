#!/bin/sh

set -e

if [ ! -d .venv ]; then
    uv venv
fi
. .venv/bin/activate
python main.py
deactivate
