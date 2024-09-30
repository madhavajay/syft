#!/bin/bash

source ./scripts/build.sh
source ./scripts/ssh.sh

LOCAL_FILE="./dist/syftbox-0.1.0-py3-none-any.whl"
REMOTE_PATH="~"

# Use scp to transfer the file to the remote server
scp -i "$KEY" "$LOCAL_FILE" "$USER@$IP:$REMOTE_PATH"

# install pip package
ssh -i "$KEY" "$USER@$IP" 'pip install --break-system-packages ~/syftbox-0.1.0-py3-none-any.whl --force'

# restart service
ssh -i "$KEY" "$USER@$IP" 'sudo systemctl daemon-reload'
ssh -i "$KEY" "$USER@$IP" 'sudo systemctl restart syftbox'

echo "Deploy successful!"
