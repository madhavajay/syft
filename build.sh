#!/bin/bash
rm -rf dist
uv build
cp dist/syftbox-0.1.0-py3-none-any.whl ./