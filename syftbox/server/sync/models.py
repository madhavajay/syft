from pydantic import BaseModel


class DiffRequest(BaseModel):
    path: str
    signature: bytes


class DiffResponse(BaseModel):
    path: str
    diff: bytes
    hash: bytes


class SignatureResponse(BaseModel):
    path: str
    signature: bytes


class SignatureRequest(BaseModel):
    path: str


class ApplyDiffRequest(BaseModel):
    path: str
    diff: bytes
    hash: bytes


class ApplyDiffResponse(BaseModel):
    path: str
    success: bool
