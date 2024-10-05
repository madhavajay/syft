#!/bin/sh

set -e

# Function to check if a command is available
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for Git dependency
if ! command_exists git; then
    echo "Error: Git is not installed or not in your PATH."
    echo "Git is required to clone repositories."
    echo "To install Git:"
    echo "  - On many Linux distributions: Use your package manager (e.g., apt, yum, dnf)"
    echo "  - On macOS: Install Xcode Command Line Tools or use Homebrew"
    echo "Please install Git and run this script again."
    exit 1
fi

# Check if the CSV file exists
if [ ! -f "github_apps.csv" ]; then
    echo "Error: github_apps.csv file not found"
    echo "Please make sure the CSV file is in the same directory as this script."
    exit 1
fi

# Read the CSV file line by line
while IFS= read -r repo_url || [ -n "$repo_url" ]; do
    # Remove any leading/trailing whitespace
    repo_url=$(echo "$repo_url" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    
    # Skip empty lines
    if [ -z "$repo_url" ]; then
        continue
    fi
    
    # Extract the repository name from the URL
    repo_name=$(echo "$repo_url" | sed -e 's/.*\///' -e 's/\.git$//')
    repo_path="../$repo_name"
    
    echo "Processing repository: $repo_name"
    echo "Local path: $repo_path"
    
    # Remove existing repository if it exists
    if [ -d "$repo_path" ]; then
        echo "Removing existing repository at $repo_path"
        rm -rf "$repo_path"
    fi
    
    # Clone the repository
    echo "Cloning $repo_url to $repo_path"
    if git clone "$repo_url" "$repo_path"; then
        echo "Successfully cloned $repo_name"
    else
        echo "Failed to clone $repo_name"
    fi
    
    echo "-----------------------------------"
done < "github_apps.csv"

echo "Process completed"