import subprocess
from pathlib import Path

ASSETS_FOLDER = Path(__file__).parents[1] / "assets"
ICONS_PKG = ASSETS_FOLDER / "icons.zip"


# Function to search for Icon\r file
def search_icon_file(src_path: Path) -> Path:
    if not src_path.exists():
        return None
    for file_path in src_path.iterdir():
        if "Icon" in file_path.name and "\r" in file_path.name:
            return file_path


# if you knew the pain of this function
def find_icon_file(src_path: Path) -> Path:
    # First attempt to find the Icon\r file
    icon_file = search_icon_file()
    if icon_file:
        return icon_file

    if not ICONS_PKG.exists():
        # If still not found, raise an error
        raise FileNotFoundError(
            "Icon file with a carriage return not found, and icon.zip did not contain it.",
        )

    try:
        # cant use other zip tools as they don't unpack it correctly
        subprocess.run(
            ["ditto", "-xk", str(ICONS_PKG), str(src_path.parent)],
            check=True,
        )

        # Try to find the Icon\r file again after extraction
        icon_file = search_icon_file()
        if icon_file:
            return icon_file
    except subprocess.CalledProcessError:
        raise RuntimeError("Failed to unzip icon.zip using macOS CLI tool.")


def copy_icon_file(icon_folder: str, dest_folder: str) -> None:
    dest_path = Path(dest_folder)
    icon_path = Path(icon_folder)
    src_icon_path = find_icon_file(icon_path)
    if not dest_path.exists():
        raise FileNotFoundError(f"Destination folder '{dest_folder}' does not exist.")

    # shutil wont work with these special icon files
    subprocess.run(["cp", "-p", src_icon_path, dest_folder], check=True)
    subprocess.run(["SetFile", "-a", "C", dest_folder], check=True)
