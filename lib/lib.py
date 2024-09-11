import json
from dataclasses import dataclass
from typing import Self

USER_GROUP_GLOBAL = "GLOBAL"


def perm_file_path(path: str) -> str:
    return f"{path}/_.syftperm"


class Jsonable:
    def to_dict(self) -> dict:
        output = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            output[k] = v
        return output

    def __iter__(self):
        for key, val in self.to_dict().items():
            if key.startswith("_"):
                yield key, val

    def __getitem__(self, key):
        if key.startswith("_"):
            return None
        return self.to_dict()[key]

    @classmethod
    def load(cls, filepath: str) -> Self:
        try:
            with open(filepath) as f:
                data = f.read()
                d = json.loads(data)
                return cls(**d)
        except Exception as e:
            print(f"Unable to load file: {filepath}. {e}")
        return None

    def save(self, filepath: str) -> None:
        d = self.to_dict()
        with open(filepath, "w") as f:
            f.write(json.dumps(d))


@dataclass
class SyftPermission(Jsonable):
    vote: list[str]
    read: list[str]
    write: list[str]
    filepath: str | None

    def __repr__(self) -> str:
        string = "SyftPerm:\n"

        string += "VOTE: ["
        for v in self.vote:
            string += v + ", "
        string += "]\n"

        string += "READ: ["
        for r in self.read:
            string += r + ", "
        string += "]\n"

        string += "READ: ["
        for w in self.write:
            string += w + ", "
        string += "]\n"
        return string

        # {
        #     "vote": ["madhava@openmined.org"],
        #     "read": ["madhava@openmined.org", "GLOBAL"],
        #     "write": ["madhava@openmined.org"],
        # }
