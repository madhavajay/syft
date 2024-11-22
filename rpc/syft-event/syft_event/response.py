from pydantic import BaseModel
from typing_extensions import Any, Mapping


class Response(BaseModel):
    content: Any = None
    status_code: int = 200
    headers: Mapping[str, str] | None = None
