import base64
from pathlib import Path
from typing import Any

import httpx

from syftbox.server.sync.models import ApplyDiffResponse, DiffResponse, FileMetadata


class SyftServerError(Exception):
    pass


class SyftNotFound(SyftServerError):
    pass


def handle_json_response(endpoint: str, response: httpx.Response) -> Any:
    # endpoint only needed for error message
    if response.status_code == 200:
        return response.json()

    raise SyftServerError(f"[{endpoint}] call failed: {response.text}")


def list_datasites(client: httpx.Client) -> list[str]:
    response = client.get(
        "/list_datasites",
    )

    data = handle_json_response("/list_datasites", response)
    return data["datasites"]


def get_remote_state(
    client: httpx.Client, email: str, path: Path
) -> list[FileMetadata]:
    response = client.post(
        "/sync/dir_state",
        params={
            "dir": str(path),
        },
    )

    response_data = handle_json_response("/dir_state", response)
    return [FileMetadata(**item) for item in response_data]


def get_metadata(client: httpx.Client, path: Path) -> FileMetadata:
    response = client.post(
        "/sync/get_metadata",
        json={
            "path_like": str(path),
        },
    )

    response_data = handle_json_response("/sync/get_metadata", response)

    if len(response_data) == 0:
        raise SyftNotFound(f"[/sync/get_metadata] not found on server: {path}")
    return FileMetadata(**response_data[0])


def get_diff(client: httpx.Client, path: Path, signature: bytes) -> DiffResponse:
    response = client.post(
        "/sync/get_diff",
        json={
            "path": str(path),
            "signature": base64.b85encode(signature).decode("utf-8"),
        },
    )

    response_data = handle_json_response("/sync/get_diff", response)
    return DiffResponse(**response_data)


def apply_diff(
    client: httpx.Client, path: Path, diff: bytes, expected_hash: str
) -> ApplyDiffResponse:
    response = client.post(
        "/sync/apply_diff",
        json={
            "path": str(path),
            "diff": base64.b85encode(diff).decode("utf-8"),
            "expected_hash": expected_hash,
        },
    )

    response_data = handle_json_response("/sync/apply_diff", response)
    return ApplyDiffResponse(**response_data)
