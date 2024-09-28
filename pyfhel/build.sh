#!/bin/bash

# curl -O https://files.pythonhosted.org/packages/2d/34/c6b1563a4c7a0fa940e5c9bfd521048bc936236e34deeb7f28cae71bf2d7/Pyfhel-3.4.2.tar.gz
# tar -xvf Pyfhel-3.4.2.tar.gz

# brew install cmake zlib llvm libomp

# # needs python 3.11
uv run --python 3.11 -- uv pip install -U pip setuptools wheel build

export CC=/opt/homebrew/opt/llvm/bin/clang
export MACOSX_DEPLOYMENT_TARGET=$(sw_vers -productVersion)

uv run --python 3.11 -- uv run python -m build Pyfhel-3.4.2
cp Pyfhel-3.4.2/dist/Pyfhel-3.4.2-cp311-cp311-macosx_13_0_arm64.whl ./
