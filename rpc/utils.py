import base64
import json
from pathlib import Path, PosixPath

import cbor2
from pydantic import BaseModel, ConfigDict
from ulid import ULID


def bytes_to_base64(data: bytes) -> str:
    """
    Convert bytes to a Base64-encoded string.

    Args:
        data (bytes): The input data in bytes.

    Returns:
        str: The Base64-encoded string.
    """
    return base64.b64encode(data).decode("utf-8")


serializers = {Path: str, PosixPath: str, ULID: str}
cbor_serializers = {}
json_serializers = {bytes: bytes_to_base64}


def get_cbor_serializers():
    return serializers | cbor_serializers


def get_json_serializers():
    return serializers | json_serializers


class CBORModel(BaseModel):
    """
    A Pydantic BaseModel subclass that provides built-in CBOR serialization
    and deserialization with dynamic type handling.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        ser_mode="python",
    )

    def model_dump(self, *args, **kwargs):
        # Custom behavior
        data = {}
        for key, value in self.__dict__.items():  # Iterate over instance fields
            print(key, value)
            t = type(value)
            serializers = get_cbor_serializers()
            if t in serializers:
                serializer = serializers[t]
                data[key] = serializer(value)
            else:
                data[key] = value
        return data

    def dump(self) -> bytes:
        """
        Serialize the model instance to CBOR format.
        """
        return cbor2.dumps(self.model_dump(mode="python"))

    @classmethod
    def load(cls, data: bytes):
        """
        Deserialize CBOR data into a model instance.
        """
        obj = cbor2.loads(data)
        return cls.parse_obj(obj)


class JSONModel(BaseModel):
    """
    A Pydantic BaseModel subclass that provides built-in JSON serialization
    and deserialization with dynamic type handling.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        ser_mode="json",
    )

    def model_dump(self, *args, **kwargs):
        data = {}
        for key, value in self.__dict__.items():  # Iterate over instance fields
            t = type(value)
            serializers = get_json_serializers()
            if t in serializers:
                serializer = serializers[t]
                data[key] = serializer(value)
            else:
                data[key] = value
        return data

    def dump(self) -> str:
        """
        Serialize the model instance to CBOR format.
        """
        return json.dumps(self.model_dump(mode="json"))

    @classmethod
    def load(cls, data: bytes):
        """
        Deserialize CBOR data into a model instance.
        """
        obj = json.loads(data)
        return cls.parse_obj(obj)
