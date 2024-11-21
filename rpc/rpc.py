import asyncio
import os
import re
import time
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from threading import Thread
from typing import Any, Mapping, Tuple
from urllib.parse import unquote

import cbor2
from app import TypeRegistry
from pydantic import field_validator
from typing_extensions import Any, Self
from ulid import ULID
from utils import CBORModel, serializers
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from syftbox.lib import SyftPermission

dispatch = {}

NOT_FOUND = 404
SERVICE_UNAVAILABLE = 503


def process_file(file_path, client):
    """Process the file that is detected."""
    print(f"Processing file: {file_path}")
    try:
        with open(file_path, "rb") as file:
            msg = Message.load(file.read())
            print("msg.path", msg.path, msg.path in dispatch)
            if msg.path in dispatch:
                route = dispatch[msg.path]
                response = route(msg)
                print("got response from function", response, type(response))
                payload = response.content
                status_code = response.status_code
            else:
                payload = None
                status_code = NOT_FOUND

            response_msg = msg.reply(payload, status_code=status_code, from_sender=client.email)
            response_msg.write(client=client, request=False)
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
            process_file(event.src_path, self.client)


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


# split to request / response
# add headers
# # path on the way out, status code on the way back
class Message(CBORModel):
    ulid: ULID
    status_code: int = 0
    url: SyftBoxURL
    sender: str
    path: str
    timestamp: int = 1
    type: str
    payload: bytes | None

    def body(self) -> Any:
        return self.payload

    def dict(self) -> dict:
        return cbor2.loads(self.payload)

    def obj(self) -> Any:
        try:
            obj = TypeRegistry[self.type].parse_obj(self.dict())
            return obj
        except Exception as e:
            print("failed to parse object", e)
            raise e

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

    def request_path(self, client):
        return self.local_path(client) / f"{self.ulid}.request"

    def response_path(self, client):
        return self.local_path(client) / f"{self.ulid}.response"

    def reply(self, payload: Any, status_code: int, from_sender: str) -> Self:
        t_name = type(payload).__name__
        if payload is None:
            data = None
        else:
            print("are we calling dump on the payload?", payload, type(payload))
            data = payload.dump()
        return Message(
            ulid=self.ulid,
            url=self.url,
            sender=from_sender,
            status_code=status_code,
            path=self.path,
            timestamp=2,
            type=t_name,
            payload=data,
        )

    def write(self, client, request: bool = True):
        if request:
            file = self.request_path(client)
        else:
            file = self.response_path(client)
        print(file, file)
        with open(file, "wb") as f:
            f.write(self.dump())


MessageBox = Tuple[int, Message | None]


def read_messsage(local_path: Path, ulid: ULID, request: bool = True) -> MessageBox:
    print("READ MESSAGE", local_path)
    path = Path(os.path.abspath(local_path))
    print(path, path)

    try:
        if not os.path.exists(local_path):
            return (SERVICE_UNAVAILABLE, None)

        with open(local_path, "rb") as file:
            msg = Message.load(file.read())
            print(msg)
            return (200, msg)
    except Exception as e:
        print("read_messsage got an error", e)
        return (500, None)


class Future(CBORModel):
    local_path: Path
    ulid: ULID
    path: Path

    def read(self):
        result = read_messsage(local_path=self.local_path, ulid=self.ulid, request=False)
        if result[0] == SERVICE_UNAVAILABLE:
            print("not ready yet waiting")
            return None
        return result[1]


class Response(CBORModel):
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


class Server:
    def __init__(self, app_name: str, client):
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


serializers[SyftBoxURL] = str

from syftbox.lib import Client

rpc_registry = RPCRegistry()


class Request:
    def __init__(self, client=None):
        if client is None:
            self.client = Client.load()
        else:
            self.client = client

    def get(self, url: str, body: Any):
        syftbox_url = SyftBoxURL(url)
        return self.send_request(syftbox_url, body)

    def send_request(self, url, body: Any):
        t_name = type(body).__name__
        data = body.dump()
        m = Message(
            ulid=ULID(), url=url, sender=self.client.email, path=url.path, timestamp=1, type=t_name, payload=data
        )
        request_path = m.request_path(self.client)
        response_path = m.response_path(self.client)

        if request_path in rpc_registry.requests:
            raise Exception(f"Already got: {request_path} in registry")

        m.write(self.client)
        rpc_registry.requests[request_path] = None
        return Future(local_path=response_path, ulid=m.ulid, path=url.path)
