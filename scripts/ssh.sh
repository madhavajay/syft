#!/bin/bash

# Define the key path and username with IP
KEY="./keys/syftbox.pem"
USER="azureuser"
IP="20.168.10.234"

# Connect to the remote machine and run the command
echo "ssh -i \"$KEY\" \"$USER@$IP\""