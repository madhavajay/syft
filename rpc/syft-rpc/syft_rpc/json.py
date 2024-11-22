import json

from pydantic import BaseModel, ConfigDict

from .serde import get_json_serializers


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
