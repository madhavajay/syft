import base64
from pathlib import Path, PosixPath

from ulid import ULID


def base64_to_bytes(data: str) -> bytes:
    return base64.b64decode(data)


def bytes_to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


serializers = {Path: str, PosixPath: str, ULID: str}
cbor_serializers = {}
json_serializers = {bytes: bytes_to_base64}


def get_cbor_serializers():
    return serializers | cbor_serializers


def get_json_serializers():
    return serializers | json_serializers
