import os
import shutil
import rumps
import json
import re
from git import Repo, GitCommandError
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

def get_or_initialize_git_repo(path='.'):
    try:
        # Check if the directory is already a Git repository
        if not os.path.exists(os.path.join(path, '.git')):
            # Initialize a new repository
            repo = Repo.init(path)
            print(f"Initialized empty Git repository in {repo.git_dir}")
        else:
            # Open the existing repository
            repo = Repo(path)
            print("This directory is already a Git repository.")
        
        # Return the repo object in either case
        return repo
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

def ensure_branches_for_directories(repo):
    try:
        # Ensure the repository has at least one commit
        if repo.head.is_detached or len(repo.branches) == 0:
            print("Repository has no commits or no branches. Creating an initial commit.")
            # Create an initial commit to ensure a valid state
            repo.index.commit("Initial commit")
        
        # Get the repository's working directory
        repo_path = repo.working_dir
        
        # List all top-level directories in the repository
        top_level_dirs = [
            d for d in os.listdir(repo_path)
            if os.path.isdir(os.path.join(repo_path, d))
        ]
        
        # Get a list of all existing branches
        existing_branches = [branch.name for branch in repo.branches]
        
        # Ensure a branch exists for each top-level directory that contains '@'
        for dir_name in top_level_dirs:
            if '@' in dir_name:
                if dir_name not in existing_branches:
                    # Create a new branch for the directory if it doesn't exist
                    repo.create_head(dir_name)
                    print(f"Created new branch: {dir_name}")
                else:
                    print(f"Branch '{dir_name}' already exists.")
        
        # Delete branches that do not contain '@'
        for branch in repo.branches:
            if '@' not in branch.name and "main" not in branch.name:
                repo.delete_head(branch, force=True)
                print(f"Deleted branch: {branch.name}")
                
    except Exception as e:
        print(f"An error occurred while ensuring branches: {str(e)}")
    
def add_ignore_rule(postfix, path='.'):
    try:
        # Define the .gitignore file path
        gitignore_path = os.path.join(path, '.gitignore')
        
        # Read the current content of .gitignore if it exists
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as gitignore_file:
                gitignore_content = gitignore_file.readlines()
        else:
            gitignore_content = []

        # Prepare the ignore rule
        ignore_rule = f"*{postfix}\n"

        # Check if the ignore rule already exists
        if ignore_rule not in gitignore_content:
            # Append the ignore rule if it doesn't exist
            with open(gitignore_path, 'a') as gitignore_file:
                gitignore_file.write(ignore_rule)
            print(f"Added rule to ignore all files with postfix '{postfix}' in {gitignore_path}")
            return True  # Indicates that the file was modified
        else:
            print(f"Ignore rule for postfix '{postfix}' already exists in {gitignore_path}")
            return False  # No modifications made
    except Exception as e:
        print(f"An error occurred while updating .gitignore: {str(e)}")
        return False

def apply_ignore_rule_to_all_branches(repo, postfix, path='.'):
    try:
        # Save the current branch
        current_branch = repo.active_branch if not repo.head.is_detached else None
        
        # Get all branches
        branches = repo.branches
        
        # Iterate through all branches
        for branch in branches:
            # Check out each branch
            repo.git.checkout(branch.name)
            print(f"Checked out branch: {branch.name}")
            
            # Apply the ignore rule
            modified = add_ignore_rule(postfix, path)
            
            # If the .gitignore file was modified, commit the change
            if modified:
                repo.index.add(['.gitignore'])
                repo.index.commit(f"Add ignore rule for files with postfix '{postfix}'")
                print(f"Committed changes to branch: {branch.name}")
        
        # Checkout the original branch again if it existed
        if current_branch:
            repo.git.checkout(current_branch.name)
            print(f"Switched back to original branch: {current_branch.name}")
        
    except GitCommandError as e:
        print(f"An error occurred while applying ignore rules to all branches: {e}")
        
def delete_main_branch(repo):
    try:
        # Check if 'main' branch exists
        if 'main' in repo.branches:
            # Ensure we're not on the 'main' branch before deleting it
            if repo.active_branch.name == 'main':
                # Checkout a different branch before deleting
                branches = [branch.name for branch in repo.branches if branch.name != 'main']
                if branches:
                    repo.git.checkout(branches[0])
                    print(f"Checked out branch: {branches[0]}")
                else:
                    print("No other branches to switch to.")
                    return
            
            # Delete the 'main' branch
            repo.delete_head('main', force=True)
            print("Deleted 'main' branch.")
        else:
            print("'main' branch does not exist.")
    except GitCommandError as e:
        print(f"An error occurred while deleting 'main' branch: {e}")        


        
def create_syft_config_in_matching_branch(repo, branches, datasite_name):
    # Ask the user for their datasite name
# while True:
    # datasite_name = input("What is your datasite name (example myfirstdatasite123@syft_cache.org)? ")

    # Validate that the datasite name loosely resembles an email address
    if re.match(r"[^@]+@[^@]+\.[^@]+", datasite_name):
        # Check if there's a branch with the same name as the datasite
        if datasite_name in branches:
            # Checkout the branch with the same name as the datasite
            repo.git.checkout(datasite_name)
            print(f"Checked out branch '{datasite_name}'")

            # Define the path to the syft.config file in this branch
            repo_path = repo.working_dir
            syft_config_path = os.path.join(repo_path, 'syft.config')

            # Get the list of top-level directories in the repository
            top_level_dirs = [
                d for d in os.listdir(repo_path)
                if os.path.isdir(os.path.join(repo_path, d))
            ]

            # Check if the datasite name matches a top-level directory
            if datasite_name in top_level_dirs:
                # Create the syft.config file with the datasite name
                config_data = {"my_datasite": datasite_name}
                with open(syft_config_path, 'w') as config_file:
                    json.dump(config_data, config_file, indent=4)
                print(f"Created syft.config with datasite name: {datasite_name} in branch '{datasite_name}'")
                return datasite_name
            else:
                # Offer to create the directory if it doesn't exist
                create_folder = input(f"The folder '{datasite_name}' does not exist. Do you want to create it? (y/n): ").lower()
                if create_folder == 'y':
                    os.makedirs(os.path.join(repo.working_dir, datasite_name))
                    print(f"Created folder: {datasite_name}")

                    # Create the syft.config file with the datasite name
                    config_data = {"my_datasite": datasite_name}
                    with open(syft_config_path, 'w') as config_file:
                        json.dump(config_data, config_file, indent=4)
                    print(f"Created syft.config with datasite name: {datasite_name} in branch '{datasite_name}'")
                    return datasite_name
                else:
                    print("Please enter a valid datasite name that corresponds to an existing top-level folder.")
        else:
            print(f"No branch named '{datasite_name}' exists. Please enter a valid datasite name.")
    else:
        print("Invalid datasite name. Please ensure it looks like an email address.")


def get_syft_config(repo, datasite_name):
    # Define the path to the syft.config file in the top-level directory
    repo_path = repo.working_dir

    # Get the list of all branches
    branches = [branch.name for branch in repo.branches]
    
    # Check each branch for the syft.config file
    for branch_name in branches:
        repo.git.checkout(branch_name)
        syft_config_path = os.path.join(repo_path, 'syft.config')

        # Check if the syft.config file exists in the branch
        if os.path.exists(syft_config_path):
            with open(syft_config_path, 'r') as config_file:
                try:
                    config_data = json.load(config_file)
                    
                    # Check if the "my_datasite" key exists
                    if "my_datasite" in config_data:
                        print(f"'syft.config' found in branch '{branch_name}'")
                        # Ensure we are in the branch corresponding to "my_datasite"
                        repo.git.checkout(config_data["my_datasite"])
                        return config_data["my_datasite"]
                except json.JSONDecodeError:
                    print(f"Error: 'syft.config' in branch '{branch_name}' is not a valid JSON file.")
                    continue

    # If no valid syft.config file is found, prompt to create it in the matching branch
    return create_syft_config_in_matching_branch(repo, branches, datasite_name)




def delete_private_key(private_key_path, branch_name):
    try:
        os.remove(private_key_path)
        print(f"Private key removed from branch '{branch_name}'.")
    except FileNotFoundError:
        print(f"Private key not found in branch '{branch_name}'.")

def create_syftperm_file(datasite_folder, public_key_path, datasite_name):
    # Define the path for the syftperm file
    syftperm_path = f"{public_key_path}.syftperm"

    # Create the syftperm file with the JSON object
    syftperm_data = {"READ": [datasite_name]}
    with open(syftperm_path, 'w') as syftperm_file:
        json.dump(syftperm_data, syftperm_file, indent=4)
    print(f"Syftperm file created at {syftperm_path}")

def check_or_create_keypair(repo, datasite_name):
    # Define paths to the datasite folder and keys
    repo_path = repo.working_dir
    datasite_folder = os.path.join(repo_path, datasite_name)
    public_key_path = os.path.join(datasite_folder, 'public_key.pem')
    private_key_path = os.path.join(datasite_folder, 'private_key.pem')

    # Check if the private key exists
    if os.path.exists(private_key_path) and os.path.exists(public_key_path):
        print("Public and private keypair already exists.")
        return
    else:
        # Offer to create the keypair if it doesn't exist
        # create_keys = input("The keypair does not exist. Do you want to create a new public and private keypair? (y/n): ").lower()
        create_keys = 'y' #TODO: prompt the user
        
        if create_keys == 'y':
            # Generate the RSA keypair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            public_key = private_key.public_key()

            # Save the private key
            with open(private_key_path, 'wb') as private_key_file:
                private_key_file.write(
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.TraditionalOpenSSL,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                )
            print(f"Private key saved to {private_key_path}")

            # Save the public key
            with open(public_key_path, 'wb') as public_key_file:
                public_key_file.write(
                    public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                )
            print(f"Public key saved to {public_key_path}")

            # Call the method to create the syftperm file
            create_syftperm_file(datasite_folder, public_key_path, datasite_name)
        else:
            print("Keypair creation skipped.")


def navigate_to_syft_config_branch(repo):
    """
    Navigates to the branch that contains the syft.config file and returns the branch name.
    Prints a warning if 'my_datasite' in syft.config does not match the branch name.
    """
    try:
        # Iterate through all branches
        for branch in repo.branches:
            repo.git.checkout(branch.name)
            syft_config_path = os.path.join(repo.working_dir, 'syft.config')
            
            # Check if the syft.config file exists in the current branch
            if os.path.exists(syft_config_path):
                with open(syft_config_path, 'r') as config_file:
                    config_data = json.load(config_file)
                    datasite_name = config_data.get("my_datasite")
                    
                    # Check if the branch name matches the 'my_datasite' value
                    if datasite_name == branch.name:
                        print(f"Navigated to the correct branch: {branch.name}")
                        return branch.name
                    else:
                        # Print a warning instead of raising an error
                        print(f"Warning: 'my_datasite' in syft.config is '{datasite_name}', "
                              f"but the branch is '{branch.name}'.")
                        return branch.name
        
        # If no branch contains the syft.config file, raise an error
        raise FileNotFoundError("No branch contains a valid syft.config file.")
    
    except json.JSONDecodeError as e:
        print(f"Error parsing syft.config: {str(e)}")
    except GitCommandError as e:
        print(f"Git command error: {str(e)}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return None

def get_files_with_syftperm(repo):
    """
    Returns a list of all files in the repository that have a corresponding .syftperm file.
    """
    files_with_syftperm = []
    repo_path = repo.working_dir
    
    try:
        # Walk through all files and directories in the repository
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                # Skip .syftperm files themselves
                if file.endswith(".syftperm"):
                    continue
                
                # Construct the corresponding .syftperm file name and path
                syftperm_file = f"{file}.syftperm"
                syftperm_file_path = os.path.join(root, syftperm_file)

                # Check if the .syftperm file exists
                if os.path.exists(syftperm_file_path):
                    # Add the original file (not the .syftperm file) to the list
                    files_with_syftperm.append(os.path.join(root, file))

        return files_with_syftperm
    except Exception as e:
        print(f"An error occurred while checking for .syftperm files: {str(e)}")
        return []

def is_file_tracked_in_branch(repo, file_path):
    """
    Checks if a file is tracked in the current branch.
    """
    try:
        # Use git ls-tree to check if the file is tracked in the current branch
        tracked_files = repo.git.ls_tree('--name-only', '-r', 'HEAD').splitlines()
        
        # Convert absolute path to relative path for comparison
        repo_path = repo.working_dir
        relative_file_path = os.path.relpath(file_path, repo_path)
        
        # Check if the relative file path is in the list of tracked files
        return relative_file_path in tracked_files
    except GitCommandError as e:
        print(f"Git error while checking if file is tracked: {str(e)}")
        return False
    except Exception as e:
        print(f"An error occurred while checking file tracking: {str(e)}")
        return False

def track_files_with_syftperm(repo, files_with_syftperm):
    """
    Ensures that all files with corresponding .syftperm files are tracked in the current branch.
    """
    try:
        for file_path in files_with_syftperm:
            # Check if the file is tracked
            if not is_file_tracked_in_branch(repo, file_path):
                # If not tracked, stage and commit the file
                print(f"File '{file_path}' is not tracked. Tracking it now...")
                repo.index.add([file_path])
                repo.index.commit(f"Add {os.path.basename(file_path)} to branch {repo.active_branch.name}")
                print(f"File '{file_path}' has been added and committed to the branch '{repo.active_branch.name}'.")
            else:
                print(f"File '{file_path}' is already tracked by the branch '{repo.active_branch.name}'.")
    except GitCommandError as e:
        print(f"Git error while trying to track files: {str(e)}")
    except Exception as e:
        print(f"An error occurred while tracking files: {str(e)}")

def navigate_to_root_datasite_and_ensure_syftperm_files_tracked(repo):
    """
    Navigates to the 'my_datasite' branch, finds all files with corresponding .syftperm files,
    and ensures that they are tracked in the branch.
    """
    try:
        # Navigate to the branch containing the syft.config file
        branch_name = navigate_to_syft_config_branch(repo)
        
        if branch_name:
            # Get the list of files with corresponding .syftperm files
            files_with_syftperm = get_files_with_syftperm(repo)
            
            # Ensure all files with .syftperm are tracked
            track_files_with_syftperm(repo, files_with_syftperm)
        else:
            print("Failed to navigate to the branch with syft.config.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

def navigate_to_root_datasite_and_commit_changes(repo):
    """
    Navigates to the 'my_datasite' branch and ensures that any file changes in the working directory are committed.
    Prints all changes being staged.
    """
    try:
        # Navigate to the branch containing the syft.config file
        branch_name = navigate_to_syft_config_branch(repo)
        
        if branch_name:
            # Check for untracked or modified files
            if repo.is_dirty(untracked_files=True):
                # Get the status of all changes
                status_output = repo.git.status(porcelain=True)
                print("Changes to be staged:")
                print(status_output)
                
                # Stage all changes (including untracked files)
                print(f"Staging all changes in branch '{branch_name}'...")
                repo.git.add(A=True)
                
                # Commit the changes
                commit_message = "Committing all changes to the 'my_datasite' branch"
                repo.index.commit(commit_message)
                print(f"All changes committed in branch '{branch_name}'.")
            else:
                print(f"No changes to commit in branch '{branch_name}'.")
        else:
            print("Failed to navigate to the branch with syft.config.")
    except GitCommandError as e:
        print(f"Git command error: {str(e)}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

import os
import json
import time
from git import GitCommandError

def get_tracked_files_in_branch(repo, branch_name):
    """
    Get a list of tracked files in the given branch.
    """
    try:
        # Checkout the branch
        repo.git.checkout(branch_name)
        
        # List tracked files in the branch
        tracked_files = repo.git.ls_tree('--name-only', '-r', 'HEAD').splitlines()
        return tracked_files
    except GitCommandError as e:
        print(f"Git command error while listing tracked files in branch '{branch_name}': {str(e)}")
        return []

def load_syft_config(repo):
    """
    Load the syft.config file and retrieve the 'my_datasite' value.
    """
    try:
        # Navigate through the branches to find the branch containing syft.config
        for branch in repo.branches:
            repo.git.checkout(branch.name)
            syft_config_path = os.path.join(repo.working_dir, 'syft.config')
            
            if os.path.exists(syft_config_path):
                with open(syft_config_path, 'r') as config_file:
                    config_data = json.load(config_file)
                    return config_data.get("my_datasite")
        raise FileNotFoundError("syft.config file not found in any branch.")
    
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading syft.config: {str(e)}")
        return None
    except GitCommandError as e:
        print(f"Git command error: {str(e)}")
        return None

def parse_syftperm_file(file_path):
    """
    Parse the .syftperm file and return the READ permissions.
    """
    try:
        with open(file_path, 'r') as syftperm_file:
            syftperm_data = json.load(syftperm_file)
            return syftperm_data.get("READ", [])
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading .syftperm file '{file_path}': {str(e)}")
        return []

def create_unique_patch_filename(branch_name, file_name):
    """
    Create a unique patch filename using the branch name and a timestamp.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{branch_name}_{file_name}_{timestamp}.patch"

def create_patch_for_single_file(repo, my_datasite_branch, outbox_dir, file_path, branch_name):
    """
    Create a patch file for a single file from the 'my_datasite' branch to the specified branch.
    Includes file additions, changes, deletions, and renames using the --diff-filter=ACDMR option.
    """
    try:
        # Create a unique patch file name
        patch_file_name = create_unique_patch_filename(branch_name, os.path.basename(file_path))
        
        # Create a directory for the branch inside the outbox (only in the my_datasite branch)
        branch_outbox_dir = os.path.join(outbox_dir, branch_name)
        if not os.path.exists(branch_outbox_dir):
            os.makedirs(branch_outbox_dir)
        
        # Patch file path
        patch_file_path = os.path.join(branch_outbox_dir, patch_file_name)
        
        # Switch to the my_datasite branch
        repo.git.checkout(my_datasite_branch)
        
        try:
            print(f"Generating patch for file: {file_path}")
            # Generate a patch that includes additions, deletions, modifications, etc.
            diff = repo.git.diff(
                f"{branch_name}..{my_datasite_branch}", 
                '--binary', 
                '--diff-filter=ACDMR', 
                '--', 
                file_path
            )
            
            if diff:
                diff += "\n"
                # Save the diff as a patch file
                with open(patch_file_path, 'w') as patch_file:
                    patch_file.write(diff)
                print(f"Patch file created: {patch_file_path}")
                return patch_file_path
            else:
                print(f"No diff found for file '{file_path}' between '{my_datasite_branch}' and '{branch_name}'.")
                return None
        
        except GitCommandError as e:
            print(f"Git error while generating patch for '{branch_name}': {str(e)}")
            return None
    
    except GitCommandError as e:
        print(f"Git command error: {str(e)}")
        return None

import os
from git import GitCommandError

def create_patch_for_deletions(repo, my_datasite_branch, outbox_dir, branch_name):
    """
    Create a patch file that captures all file deletions from the 'my_datasite' branch to the specified branch.
    """
    try:
        # Create a unique patch file name
        patch_file_name = create_unique_patch_filename(branch_name, "deletions")
        
        # Create a directory for the branch inside the outbox (only in the my_datasite branch)
        branch_outbox_dir = os.path.join(outbox_dir, branch_name)
        if not os.path.exists(branch_outbox_dir):
            os.makedirs(branch_outbox_dir)
        
        # Patch file path
        patch_file_path = os.path.join(branch_outbox_dir, patch_file_name)
        
        # Switch to the my_datasite branch
        repo.git.checkout(my_datasite_branch)
        
        try:
            print(f"Generating deletion patch for branch: {branch_name}")
            # Generate a patch that only includes deletions
            diff = repo.git.diff(
                f"{branch_name}..{my_datasite_branch}", 
                '--binary', 
                '--diff-filter=D'  # Only include file deletions
            )
            
            if diff:
                diff += "\n"
                # Save the diff as a patch file
                with open(patch_file_path, 'w') as patch_file:
                    patch_file.write(diff)
                print(f"Deletion patch file created: {patch_file_path}")
                return patch_file_path
            else:
                print(f"No deletions found between '{my_datasite_branch}' and '{branch_name}'.")
                return None
        
        except GitCommandError as e:
            print(f"Git error while generating deletion patch for '{branch_name}': {str(e)}")
            return None
    
    except GitCommandError as e:
        print(f"Git command error: {str(e)}")
        return None

    
def apply_patch_to_branch(repo, patch_file_path, branch_name, file_path=None):
    """
    Apply the generated patch to the target branch using 'git apply'.
    Ensure that the outbox folder remains untracked in the target branches.
    """
    try:

        # Checkout the target branch
        repo.git.checkout(branch_name)
        print(f"Applying patch to branch '{branch_name}'...")

        # Apply the patch using 'git apply'
        repo.git.apply(patch_file_path)
        print(f"Patch applied successfully to branch '{branch_name}'.")

        # # Stage all changes. If file_path is none then it means this is a deletion patch
        if file_path is not None:
            repo.git.add(file_path)

        # Commit the changes
        repo.index.commit(f"Applied patch from '{patch_file_path}'")
        print(f"Patch committed to branch '{branch_name}'.")

        # After all patches are created and applied, navigate back to the my_datasite branch
        repo.git.checkout(my_datasite_branch)
        print(f"Returned to the '{my_datasite_branch}' branch.")
    

    except GitCommandError as e:
        print(f"Git error while applying patch to branch '{branch_name}': {str(e)}")
    except Exception as e:
        print(f"An unexpected error occurred while applying the patch: {str(e)}")

def create_and_apply_patches_for_new_files(repo, outbox_dir):
    """
    Create patches for new files and file changes in the 'my_datasite' branch and apply them to all other branches.
    Generate patches for one file at a time and save them in the outbox directory.
    Ensure the outbox folder is only in the my_datasite branch.
    """
    try:
        # Load the my_datasite branch from syft.config
        my_datasite_branch = load_syft_config(repo)

        print("checking out my_datasite_branch:" + str(my_datasite_branch))
        # Checkout the my_datasite branch
        repo.git.checkout(my_datasite_branch)

        # Create the outbox directory in the my_datasite branch if it doesn't exist
        if not os.path.exists(outbox_dir):
            os.makedirs(outbox_dir)


        # Get tracked files in the 'my_datasite' branch
        my_datasite_tracked_files = get_tracked_files_in_branch(repo, my_datasite_branch)


        # Get all branches except 'my_datasite' branch
        branches = [branch.name for branch in repo.branches if branch.name != my_datasite_branch]

        for branch_name in branches:

            # for branch_name in branches:
            print(f"Comparing branch '{my_datasite_branch}' with '{branch_name}'...")

            # Get tracked files in the current branch
            branch_tracked_files = get_tracked_files_in_branch(repo, branch_name)


            repo.git.checkout(my_datasite_branch)


            # Identify new files and changed files in 'my_datasite' branch that are not in the current branch
            # new_or_changed_files = set(my_datasite_tracked_files) - set(branch_tracked_files)

            patch_filepaths = list()

            for file_path in my_datasite_tracked_files:
                syftperm_file = f"{file_path}.syftperm"
                syftperm_file_path = os.path.join(repo.working_dir, syftperm_file)

                # Check if the .syftperm file exists and has the branch in the READ key
                if os.path.exists(syftperm_file_path):
                    read_permissions = parse_syftperm_file(syftperm_file_path)
                    if branch_name in read_permissions:
                        print(f"Creating patch for file '{file_path}' to branch '{branch_name}'...")
                        patch_file_path = create_patch_for_single_file(repo, my_datasite_branch, outbox_dir, file_path, branch_name)
                        if patch_file_path:
                            patch_filepaths.append((patch_file_path, branch_name, file_path))

            # because we're looking file by file — we won't see files which have
            # been deleted, so we need to do a scan
            patch_file_path = create_patch_for_deletions(repo, my_datasite_branch, outbox_dir, branch_name)       
            if patch_file_path:
                patch_filepaths.append((patch_file_path, branch_name, None))                
                            
            for patch_filepath, branch_name, file_path in patch_filepaths:
                apply_patch_to_branch(repo, patch_filepath, branch_name, file_path)

        # After all patches are created and applied, navigate back to the my_datasite branch
        repo.git.checkout(my_datasite_branch)
        print(f"Returned to the '{my_datasite_branch}' branch.") 
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        
class SyftBox(rumps.App):
    
    def __init__(self):
        self.config_folder()
        self.config_datasite()
        self.repo = get_or_initialize_git_repo(self.folder_path)
        self.update_branches()
        delete_main_branch(self.repo)
        get_syft_config(self.repo, self.datasite)
        check_or_create_keypair(self.repo, self.datasite)
        navigate_to_root_datasite_and_ensure_syftperm_files_tracked(self.repo)
        navigate_to_root_datasite_and_commit_changes(self.repo)
        create_and_apply_patches_for_new_files(self.repo,
                                               outbox_dir=self.folder_path+"/outbox")
        
        # Initialize the app with the selected folder and icon
        super(SyftBox, self).__init__(
            "SyftBox",
            icon="mark-primary-trans.png",
            menu=["Config"]
        )

    def update_branches(self):
        
        ensure_branches_for_directories(self.repo)
        apply_ignore_rule_to_all_branches(repo=self.repo, 
                                          postfix='.patch',
                                          path=self.folder_path)    
        apply_ignore_rule_to_all_branches(repo=self.repo, 
                                          postfix='outbox',
                                          path=self.folder_path) 
        
    def config_datasite(self):
        datasite = rumps.Window(
            title="Choose Datasite",
            message="Please specify the name of your datasite:",
            default_text="andrew@syft_cache.org",
            ok="Confirm",
            cancel="Cancel",
            dimensions=(320, 20)
        ).run()
        
        # If the user cancels, exit the application
        if not datasite.clicked:
            rumps.alert("No datasite specified. Exiting application.")
            rumps.quit_application()        
            
        self.datasite = os.path.expanduser(datasite.text)
        self.datasite_path = os.path.join(self.folder_path, self.datasite)
        
        # Create the folder if it doesn't exist
        if not os.path.exists(self.datasite_path):
            os.makedirs(self.datasite_path)
        
        
    def config_folder(self):
        # Ask the user to confirm or specify the folder to use
        default_folder = os.path.expanduser("~/SyftBox/")
        folder = rumps.Window(
            title="Choose Folder",
            message="Please confirm the folder to use (default is ~/SyftBox/):",
            default_text=default_folder,
            ok="Confirm",
            cancel="Cancel",
            dimensions=(320, 20)
        ).run()

        # If the user cancels, exit the application
        if not folder.clicked:
            rumps.alert("No folder selected. Exiting application.")
            rumps.quit_application()

        self.folder_path = os.path.expanduser(folder.text)

        # Delete the folder if it already exists
        if os.path.exists(self.folder_path):
            try:
                shutil.rmtree(self.folder_path)
                print(f"Deleted existing folder: {self.folder_path}")
            except Exception as e:
                rumps.alert(f"Error deleting folder: {e}")
                rumps.quit_application()

        # Create the folder afresh
        os.makedirs(self.folder_path)

    @rumps.clicked("Config")
    def say_hello(self, _):
        rumps.alert(f"Using folder: {self.folder_path}")

if __name__ == "__main__":
    SyftBox().run()
