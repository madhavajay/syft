import asyncio
import base64
import json
import os
import re
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from typing import Any, Mapping
from urllib.parse import unquote

import cbor2
from pydantic import BaseModel, field_validator
from typing_extensions import Any, Self
from ulid import ULID
from utils import JSONModel, serializers
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from syftbox.lib import Client, SyftPermission

dispatch = {}

NOT_FOUND = 404


def base64_to_bytes(data: str) -> bytes:
    """
    Convert a Base64-encoded string to bytes.

    Args:
        data (str): The Base64-encoded string.

    Returns:
        bytes: The decoded bytes.
    """
    return base64.b64decode(data)


def process_request(file_path, client):
    """Process the file that is detected."""
    print(f"Processing file: {file_path}")
    try:
        with open(file_path, "rb") as file:
            msg = RequestMessage.load(file.read())
            print("msg.path", msg.url_path, msg.url_path in dispatch)
            if msg.url_path in dispatch:
                route = dispatch[msg.url_path]
                response = route(msg)
                print("got response from function", response, type(response))
                body = response.content
                headers = response.headers
                status_code = response.status_code
            else:
                body = b""
                headers = {}
                status_code = NOT_FOUND

            response_msg = msg.reply(from_sender=client.email, body=body, headers=headers, status_code=status_code)
            response_msg.send(client=client)
    except Exception as e:
        import traceback

        print(traceback.format_exc())
        print(f"Failed to process request: {file_path}. {e}")


class FileWatcherHandler(FileSystemEventHandler):
    """Handles events in the watched directory."""

    def __init__(self, client):
        super().__init__()
        self.client = client

    def on_created(self, event):
        if event.is_directory:
            return
        print(f"New file detected: {event.src_path}")
        if event.src_path.endswith(".request"):
            process_request(event.src_path, self.client)


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


class Response(JSONModel):
    content: Any = None
    status_code: int = 200
    headers: Mapping[str, str] | None = None


def listen(listen_path, client):
    event_handler = FileWatcherHandler(client)
    observer = Observer()
    observer.schedule(event_handler, listen_path, recursive=True)
    observer.start()
    print(f"Watching directory: {listen_path}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping observer...")
        observer.stop()
    observer.join()


# Wrapper to run the listener in a thread
def start_listener_in_thread(listen_path, client):
    listener_thread = Thread(target=listen, args=(listen_path, client), daemon=True)
    listener_thread.start()
    print("File watcher started in a separate thread.")


def cleanup_old_files(listen_path: Path, message_timeout: int):
    """
    Cleans up files in the listen path that are older than 1 minute, except for the file `_.syftperm`.

    Args:
        listen_path (Path): The directory to clean up.
    """
    now = time.time()
    for file in listen_path.glob("*"):
        if file.name == "_.syftperm":
            continue
        if file.is_file():
            file_age = now - file.stat().st_mtime
            if file_age > message_timeout:  # Older than 1 minute
                try:
                    file.unlink()
                    print(f"Deleted old file: {file}")
                except Exception as e:
                    print(f"Failed to delete file {file}: {e}")


def start_cleanup_in_thread(listen_path: Path, message_timeout: int):
    """
    Starts a thread that runs the cleanup process every 1 minute.

    Args:
        listen_path (Path): The directory to clean up.
    """

    def cleanup_loop():
        while True:
            cleanup_old_files(listen_path, message_timeout)
            time.sleep(1)  # Run cleanup every 1 minute

    cleanup_thread = Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()
    print("Cleanup process started in a separate thread.")


class Server:
    def __init__(self, app_name: str, client, message_timeout=60):
        self.client = client
        self.datasites_path = client.datasites
        self.datasite = client.email
        self.own_datasite_path = client.datasites / client.email
        self.app_name = app_name
        self.public_listen_path = self.own_datasite_path / "public" / "rpc" / self.app_name / "listen"
        # create listen dir
        os.makedirs(self.public_listen_path, exist_ok=True)
        permission = SyftPermission.mine_with_public_write(email=self.datasite)
        permission.ensure(self.public_listen_path)
        start_listener_in_thread(self.public_listen_path, self.client)
        start_cleanup_in_thread(self.public_listen_path, message_timeout)
        print(f"Listening on: {self.public_listen_path}")

    def register(self, path: str, func):
        print(f"Registering path: {path}")
        dispatch[path] = func

    def get(self, path: str):
        def decorator(function: Callable):
            self.register(path, function)
            return function

        return decorator

    async def run_forever(self):
        """Keeps the event loop running indefinitely."""
        try:
            while True:
                await asyncio.sleep(1)  # Keeps the event loop alive
        except asyncio.CancelledError:
            print("Shutting down gracefully...")

    def run(self):
        """Starts the server and blocks until interrupted."""
        loop = asyncio.get_event_loop()

        try:
            print("Server is running. Press Ctrl+C to stop.")
            loop.run_until_complete(self.run_forever())
        except KeyboardInterrupt:
            print("Keyboard interrupt received. Exiting...")
        finally:
            loop.run_until_complete(self.shutdown())
            loop.close()

    async def shutdown(self):
        """Custom shutdown logic."""
        print("Cleaning up resources...")


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
