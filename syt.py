import os
from pathlib import Path
import json
from git import Repo
import datetime

READ_PERMISSION = "r"
WRITE_PERMISSION = "w"

default_permissions = {READ_PERMISSION:[], WRITE_PERMISSION: []}

def git_repo_path_for_user(user, syft_home=SYFT_HOME):
    return syft_home / user

def git_repo_for_user(user, syft_home=SYFT_HOME):
    git_path = git_repo_path_for_user(user, syft_home=syft_home)
    repo = Repo(git_path)
    return repo

def user_permission_allowed(permissions, user, permission):
    perm = permissions[permission]
    return user in perm or "*" in perm

def validate_perm_file(perm_file_path, user):
    # trigger warning
    with open(perm_file_path, "r") as f:
        perms = default_permissions
        try:
            json_data = json.loads(f.read())
        except Exception as e:
            json_data = perms
        perms.update(json_data)
        
    allowed = user_permission_allowed(perms, user, WRITE_PERMISSION)
    if not allowed:
        file_path = str(perm_file_path).replace(".syftperm", "")
        raise Exception(f"User: {user} does not have {WRITE_PERMISSION} for {file_path}")

def validate_diffs(file_paths, user_repo, as_user) -> bool:
    # split perm and non perm folder / files from the diff
    permission_file_paths = {}
    actual_file_paths = {}
    
    # build the two dicts
    for path in file_paths:
        if path.endswith(".syftperm"):
            actual = path.replace(".syftperm", "")
            if path not in permission_file_paths:
                permission_file_paths[path] = actual
            if path not in actual_file_paths:
                actual_file_paths[actual] = path
        else:
            perm = path + ".syftperm"
            if path not in permission_file_paths:
                permission_file_paths[perm] = path
            if path not in actual_file_paths:
                actual_file_paths[path] = perm
    user_path = git_repo_path_for_user(user_repo)
    for path in actual_file_paths.keys():
        file_path = user_path / Path(path)
        exists = True if os.path.exists(file_path) else False
        if not exists:
            raise Exception(f"File missing: {file_path}")
        is_dir = True if os.path.isdir(file_path) else False
        name = "folder" if is_dir else "file"
        print(f"Validating {name}: {path}")
        perm_file = actual_file_paths[path]
        perm_file_path = user_path / Path(perm_file)
        if not os.path.exists(perm_file_path):
            raise Exception(f"Missing perm file for user: {path} at: {user_path}/{perm_file}")

        validate_perm_file(perm_file_path, as_user)
    return True

def syt_stage(repo_user, as_user):
    patches_dir = f"./patch_{repo_user}"
    os.makedirs(patches_dir, exist_ok=True)
    repo = git_repo_for_user(repo_user)
    file_diffs = repo.head.commit.diff(None)
    if len(file_diffs) == 0:
        print("Nothing to commit")
        return False
    file_paths = [diff.b_path for diff in file_diffs]
    return validate_diffs(file_paths, repo_user, as_user)

def syt_commit(repo_user, as_user, message):
    patches_dir = f"./patch_{repo_user}"
    repo = git_repo_for_user(repo_user)
    if not syt_stage(repo_user, as_user):
        return

    new_commit = repo.index.commit(message)

    commit_hash = new_commit.hexsha
    print(f"Commit hash: {commit_hash}")

    existing_files = [f for f in os.listdir(patches_dir) if commit_hash in f]
    if existing_files:
        print(f"Patch with the commit hash: {commit_hash} already exists")
        return
    patch_content = repo.git.show(new_commit)

    current_timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    patch_file = f"{patches_dir}/{current_timestamp}-{commit_hash}"
    print(f"Writing patch to:{patch_file}")

    with open(patch_file, "w") as f:
        f.write(patch_content)


def get_patch_path(commit_hash) -> str:
    patch_dirs = [d for d in os.listdir("./") if "patch_" in d]
    for patch_dir in patch_dirs:
        patches_dir = Path(patch_dir)
        existing_files = [f for f in os.listdir(patches_dir) if commit_hash in f]
        if existing_files:
            return patches_dir / existing_files[0]
    return None

def extract_email(commit_path) -> str:
    with open(commit_path, "r") as f:
        lines = f.read()
    # print(lines)
    import re
    email_pattern = re.compile(r'Author: .* <(.*?)>')
        # Search for the email in the git patch
    match = email_pattern.search("".join(lines))
    
    if match:
        email = match.group(1)
        return email
    else:
        print("No email found.")
    return None

def get_all_patch_files(commit_path) -> list[str]:
    from unidiff import PatchSet
    with open(patch_file, "r") as f:
        lines = f.readlines()
        patch = PatchSet(lines)
    return [patch_file.path for patch_file in patch]

def apply_patch(commit_hash, repo_user):
    commit_path = get_patch_path(commit_hash)
    patch_files = get_all_patch_files(commit_path)
    author = extract_email(commit_path)
    as_user = author_user[author]
    validate_diffs(patch_files, repo_user, as_user)
    repo = git_repo_for_user(repo_user)
    commit_path = os.path.abspath(commit_path)
    print(f"Applying patch: {commit_hash} from {as_user}")
    try:
        repo.git.apply(commit_path)
    except Exception as e:
        if "patch does not apply" in str(e):
            print("Patch already applied")
            return
        raise e