import os
import subprocess
import csv
import time

LAST_UPDATE_FILE = ".last_updates"

def command_exists(command):
    """Check if a command exists in the system."""
    return subprocess.call(["type", command], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

def get_last_update(repo_name):
    """Retrieve the last update timestamp for a given repository."""
    if os.path.isfile(LAST_UPDATE_FILE):
        with open(LAST_UPDATE_FILE, 'r') as f:
            for line in f:
                name, timestamp = line.strip().split(',')
                if name == repo_name:
                    return int(timestamp)
    return None

def set_last_update(repo_name):
    """Set the current timestamp as the last update time for a given repository."""
    current_time = int(time.time())
    lines = []
    if os.path.isfile(LAST_UPDATE_FILE):
        with open(LAST_UPDATE_FILE, 'r') as f:
            lines = f.readlines()
    with open(LAST_UPDATE_FILE, 'w') as f:
        for line in lines:
            if not line.startswith(f"{repo_name},"):
                f.write(line)
        f.write(f"{repo_name},{current_time}\n")

def should_update(repo_name, update_frequency):
    """Determine if a repository should be updated based on the update frequency."""
    last_update = get_last_update(repo_name)
    if last_update is None:
        return True
    current_time = int(time.time())
    return (current_time - last_update) >= int(update_frequency)

def main():
    """Main function to manage the update process of GitHub repositories."""
    if not command_exists("git"):
        print("Error: Git is not installed or not in your PATH.")
        print("Git is required to clone repositories.")
        print("Please install Git and run this script again.")
        return

    if not os.path.isfile("github_apps.csv"):
        print("Error: github_apps.csv file not found")
        print("Please make sure the CSV file is in the same directory as this script.")
        return

    with open("github_apps.csv", newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row or not row[0].strip():
                continue

            repo_url = row[0].strip()
            update_frequency = row[1].strip()
            update_type = row[2].strip()

            repo_name = repo_url.split('/')[-1].replace('.git', '')
            repo_path = f"../{repo_name}"

            if not should_update(repo_name, update_frequency):
                print(f"Skipping {repo_name}, not time to update yet")
                continue

            print(f"Processing repository: {repo_name}")
            print(f"Local path: {repo_path}")
            print(f"Update frequency: every {update_frequency} seconds")
            print(f"Update type: {update_type}")

            if os.path.isdir(repo_path):
                if update_type == "REPLACE":
                    print(f"Removing existing repository at {repo_path}")
                    subprocess.call(["rm", "-rf", repo_path])
                    print(f"Cloning {repo_url} to {repo_path}")
                    if subprocess.call(["git", "clone", repo_url, repo_path]) == 0:
                        print(f"Successfully cloned {repo_name}")
                    else:
                        print(f"Failed to clone {repo_name}")
                elif update_type == "GIT PULL":
                    print(f"Updating existing repository at {repo_path}")
                    current_dir = os.getcwd()
                    os.chdir(repo_path)
                    if subprocess.call(["git", "status", "--porcelain"], stdout=subprocess.PIPE):
                        print("Changes detected, stashing it before pull")
                        subprocess.call(["git", "stash"])
                    else:
                        print("No changes to commit")
                    try:
                        if subprocess.run(["git", "pull", "origin", "main"], check=True) == 0:
                            subprocess.call(["git", "stash", "pop"])
                            print(f"Successfully updated {repo_name}")
                        else:
                            print(f"Failed to update {repo_name}")
                    except Exception as e:
                        print(e.stderr)
                    os.chdir(current_dir)
                else:
                    print(f"Invalid update type for {repo_name}: {update_type}")
            else:
                print(f"Cloning {repo_url} to {repo_path}")
                if subprocess.call(["git", "clone", repo_url, repo_path]) == 0:
                    print(f"Successfully cloned {repo_name}")
                else:
                    print(f"Failed to clone {repo_name}")

            set_last_update(repo_name)
            print("-----------------------------------")

    print("Process completed")

if __name__ == "__main__":
    main()
