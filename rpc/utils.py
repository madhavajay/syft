from pathlib import Path, PosixPath

import cbor2
from pydantic import BaseModel, ConfigDict
from ulid import ULID

serializers = {Path: str, PosixPath: str, ULID: str}


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
