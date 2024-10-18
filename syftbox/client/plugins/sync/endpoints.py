from pathlib import Path
from typing import Any

import httpx

from syftbox.lib import Client, DirState


class SyftServerError(Exception):
    pass


def handle_json_response(endpoint: str, response: httpx.Response) -> Any:
    if response.status_code == 200:
        return response.json()

    raise SyftServerError(f"Failed to call {endpoint} on the server: {response.text}")


def list_datasites(client: Client) -> list[str]:
    response = client.server_client.get(
        "/list_datasites",
    )

    data = handle_json_response(response)
    return data["datasites"]


def get_remote_state(client: Client, path: Path) -> DirState:
    response = client.server_client.post(
        "/dir_state",
        json={
            "email": client.email,
            "sub_path": str(path),
        },
    )

    response_data = handle_json_response(response)
    return DirState(**response_data["dir_state"])
