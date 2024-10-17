import base64
import hashlib
from pathlib import Path

import py_fast_rsync
from fastapi import APIRouter, Depends, HTTPException

from syftbox.server.settings import ServerSettings, get_server_settings
from syftbox.server.sync.hash import hash_file

from .models import (
    ApplyDiffRequest,
    ApplyDiffResponse,
    DiffRequest,
    DiffResponse,
    FileMetadata,
    SignatureRequest,
    SignatureResponse,
)


def get_file_metadata(
    req: SignatureRequest,
    server_settings: ServerSettings = Depends(get_server_settings),
) -> FileMetadata:
    path = Path(req.path)

    if path.absolute() == path:
        raise HTTPException(status_code=400, detail="path must be relative")

    abs_path = server_settings.snapshot_folder.absolute() / path
    if not abs_path.exists():
        raise HTTPException(status_code=400, detail="path does not exist")
    metadata = hash_file(server_settings.snapshot_folder.absolute(), abs_path)

    # TODO check permissions
    return metadata


router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/get_diff", response_model=DiffResponse)
async def get_diff(
    req: DiffRequest,
    metadata: FileMetadata = Depends(get_file_metadata),
) -> DiffResponse:
    with open(metadata.path, "rb") as f:
        data = f.read()

    # also load from cache
    diff = py_fast_rsync.diff(req.signature_bytes, data)
    diff_bytes = base64.b85encode(diff).decode("utf-8")
    return DiffResponse(
        path=metadata.relative_path.as_posix(),
        diff=diff_bytes,
        hash=metadata.hash,
    )


@router.post("/get_signature", response_model=SignatureResponse)
async def get_signature(
    metadata: FileMetadata = Depends(get_file_metadata),
) -> SignatureResponse:
    return SignatureResponse(
        # convert to relative path to syftbox
        path=metadata.relative_path.as_posix(),
        signature=metadata.signature,
    )


@router.post("/apply_diff", response_model=ApplyDiffResponse)
async def apply_diffs(
    req: ApplyDiffRequest,
    metadata: FileMetadata = Depends(get_file_metadata),
) -> ApplyDiffResponse:
    # do it in parallel?
    # how does it work with multiple writers
    # should work in a transaction
    with open(metadata.path, "rb") as f:
        data = f.read()

    # document the behaviour instead of
    result = py_fast_rsync.apply(data, req.diff_bytes)
    sha256 = hashlib.sha256(result).hexdigest()
    if sha256 != req.expected_hash:
        raise HTTPException(status_code=400, detail="expected_hash mismatch")

    # when could write fail?
    # - no diskspace
    with open(req.path, "wb") as f:
        f.write(result)

    # TODO update hash and signature

    return ApplyDiffResponse(
        path=req.path, current_hash=sha256, previous_hash=metadata.hash
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(router, host="127.0.0.1", port=8000)
