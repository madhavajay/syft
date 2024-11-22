from syft_rpc import JSONModel
from syft_rpc import Future


class User(JSONModel):
    id: int
    name: str


class LoginResponse(JSONModel):
    username: str
    token: int = 123


TypeRegistry = {"User": User, "LoginResponse": LoginResponse}


def to_obj(obj, headers):
    if "object-type" in headers and headers["object-type"] in TypeRegistry:
        constructor = TypeRegistry[headers["object-type"]]
        return constructor(**obj)


def body_to_obj(message):
    if isinstance(message, Future):
        message = message.wait()
    return to_obj(message.decode(), message.headers)
