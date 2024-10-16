import hashlib

import py_fast_rsync
from fastapi import APIRouter

from .models import (
    ApplyDiffRequest,
    DiffRequest,
    DiffResponse,
    SignatureRequest,
    SignatureResponse,
)

app = APIRouter(
    prefix="/rsync",
    tags=["rsync"],
)


@app.post("/get_diffs", response_model=list[DiffResponse])
async def get_diffs(diff_requests: list[DiffRequest]) -> list[DiffResponse]:
    response_diffs = []
    for diff in diff_requests:
        with open(diff.path, "rb") as f:
            data = f.read()

        # not ideal for large files
        # but py_fast_rsync does not support files yet.
        # TODO: add support for files
        delta = py_fast_rsync.diff(diff.signature, data)

        # TODO: load from cache/db
        hash_server = hashlib.sha256(data).hexdigest()

        response_diffs.append(
            DiffResponse(
                path=diff.path,
                diff=delta,
                hash=hash_server,
            )
        )
    return response_diffs


@app.get("/get_signatures", response_model=list[SignatureResponse])
async def get_signatures(
    signature_requests: list[SignatureRequest],
) -> list[SignatureResponse]:
    pass


@app.post("/apply_diffs")
async def apply_diffs(diff_requests: list[ApplyDiffRequest]) -> None:
    pass
