import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import cbor2
from pydantic import BaseModel, field_validator
from typing_extensions import Any, Self
from ulid import ULID

from syftbox.lib import Client

from .json import JSONModel
from .serde import base64_to_bytes, serializers


class RPCRegistry:
    requests: dict[str, str | None] = defaultdict(lambda: None)


class SyftBoxURL:
    def __init__(self, url: str):
        self.url = url
        self._validate_url()
        self._parsed_url = self._parse_url()

    def _validate_url(self):
        """Validates the given URL matches the syft:// protocol and email-based schema."""
        pattern = r"^syft://([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)(/.*)?$"
        if not re.match(pattern, self.url):
            raise ValueError(f"Invalid SyftBoxURL: {self.url}")

    def _parse_url(self):
        """Parses the URL using `urlparse` and custom logic for extracting the email."""
        url_without_protocol = self.url[len("syft://") :]
        email, _, path = url_without_protocol.partition("/")
        return {"protocol": "syft://", "host": email, "path": f"/{path}" if path else "/"}

    @property
    def protocol(self):
        """Returns the protocol (syft://)."""
        return self._parsed_url["protocol"]

    @property
    def host(self):
        """Returns the host, which is the email part."""
        return self._parsed_url["host"]

    @property
    def path(self):
        """Returns the path component after the email."""
        return unquote(self._parsed_url["path"])

    def to_local_path(self, datasites_path: Path) -> Path:
        """
        Converts the SyftBoxURL to a local file system path.

        Args:
            datasites_path (Path): Base directory for datasites.

        Returns:
            Path: Local file system path.
        """
        # Remove the protocol and prepend the datasites_path
        local_path = datasites_path / self.host / self.path.lstrip("/")
        return local_path.resolve()

    def __repr__(self):
        return f"{self.protocol}{self.host}{self.path}"


serializers[SyftBoxURL] = str


def mk_timestamp() -> float:
    return datetime.now(timezone.utc).timestamp()


class Message(JSONModel):
    ulid: ULID
    sender: str
    headers: dict[str, str]
    timestamp: float = mk_timestamp()
    body: bytes | None
    url: SyftBoxURL

    @property
    def url_path(self):
        return self.url.path

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: Any) -> SyftBoxURL:
        """
        Custom field validator for 'url' to convert a string to SyftBoxURL.
        """
        if isinstance(value, str):
            return SyftBoxURL(value)
        if isinstance(value, SyftBoxURL):
            return value
        raise ValueError(f"Invalid type for url: {type(value)}. Expected str or SyftBoxURL.")

    def local_path(self, client):
        return self.url.to_local_path(client.workspace.datasites)

    def file_path(self, client):
        return self.local_path(client) / f"{self.ulid}.{self.message_type}"

    def decode(self):
        if "content-type" in self.headers:
            if self.headers["content-type"] == "application/json":
                try:
                    b = base64_to_bytes(self.body)
                    return json.loads(b)
                except Exception as e:
                    raise e
            if self.headers["content-type"] == "application/cbor":
                try:
                    return cbor2.loads(self.body)
                except Exception as e:
                    raise e
        else:
            return self.body.decode("utf-8")

    def send(self, client):
        file = self.file_path(client)
        with open(file, "wb") as f:
            output = self.dump()
            if isinstance(output, str):
                output = output.encode("utf-8")
            f.write(output)


class ResponseMessage(Message):
    message_type: str = "response"
    status_code: int = 200


class RequestMessage(Message):
    message_type: str = "request"

    def reply(
        self, from_sender: str, body: object | str | bytes, headers: dict[str, str] | None, status_code: int = 200
    ) -> Self:
        if headers is None:
            headers = {}
        if isinstance(body, str):
            body = body.encode("utf-8")
        elif hasattr(body, "dump"):
            body = body.dump()
        elif not isinstance(body, bytes):
            raise Exception(f"Invalid body type: {type(body)}")

        return ResponseMessage(
            ulid=self.ulid,
            sender=from_sender,
            headers=headers,
            status_code=status_code,
            timestamp=mk_timestamp(),
            body=body,
            url=self.url,
        )


def read_response(local_path: Path) -> ResponseMessage | None:
    try:
        if not os.path.exists(local_path):
            # not ready
            return None

        with open(local_path, "rb") as file:
            return Message.load(file.read())
    except Exception as e:
        print("read_messsage got an error", e)
        raise e


class Future(BaseModel):
    local_path: Path
    value: Any = None

    def wait(self, timeout=5):
        start = time.time()
        while time.time() - start < timeout:
            self.check(silent=True)
            if self.value is not None:
                return self.value
            time.sleep(0.1)
        raise Exception("Timeout waiting for response")

    @property
    def resolve(self):
        if self.value is None:
            self.check()
        return self.value

    def check(self, silent=False):
        result = read_response(local_path=self.local_path)
        if result is None:
            if not silent:
                print("not ready yet waiting")
        self.value = result


rpc_registry = RPCRegistry()


class Request:
    def __init__(self, client=None):
        if client is None:
            self.client = Client.load()
        else:
            self.client = client

    def get(self, url: str, body: Any, headers: dict[str, str] | None = None) -> Future:
        syftbox_url = SyftBoxURL(url)
        return self.send_request(syftbox_url, body=body, headers=headers)

    def send_request(self, url, body: Any, headers: dict[str, str] | None = None) -> Future:
        if headers is None:
            headers = {}
        m = RequestMessage(
            ulid=ULID(),
            url=url,
            sender=self.client.email,
            timestamp=mk_timestamp(),
            body=body,
            headers=headers,
        )
        request_path = m.file_path(self.client)
        if request_path in rpc_registry.requests:
            raise Exception(f"Already sent request: {request_path}")

        response_path = Path(str(request_path).replace("request", "response"))
        m.send(self.client)
        rpc_registry.requests[request_path] = None
        return Future(local_path=response_path)
