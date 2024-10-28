from pathlib import Path

from typing_extensions import TypeAlias, Union

PathLike: TypeAlias = Union[str, Path]


class SyftWorkspace:
    """
    A Syft workspace is a directory structure for everything stored by the client.
    Each workspace is expected to be unique for a client.
    """

    def __init__(self, root_dir: PathLike):
        self.data_dir = Path(root_dir).expanduser().resolve()

        # datasites dir
        self.datasites = self.data_dir / "datasites"

        # plugins dir
        self.plugins = self.data_dir / "plugins"

        # apps dir
        self.apps = self.data_dir / "apps"

    def mkdirs(self):
        self.datasites.mkdir(parents=True, exist_ok=True)
        self.plugins.mkdir(parents=True, exist_ok=True)
        self.apps.mkdir(parents=True, exist_ok=True)
