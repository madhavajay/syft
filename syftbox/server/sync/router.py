import base64
import hashlib
import sqlite3
import tempfile
from pathlib import Path

import py_fast_rsync
from fastapi import APIRouter, Depends, HTTPException, Request
from py_fast_rsync import signature

from syftbox.server.settings import ServerSettings, get_server_settings
from syftbox.server.sync.db import get_all_metadata, get_db, move_with_transaction

from .models import (
    ApplyDiffRequest,
    ApplyDiffResponse,
    DiffRequest,
    DiffResponse,
    FileMetadata,
    FileMetadataRequest,
)


def get_db_connection(request: Request):
    conn = get_db(request.state.server_settings.file_db_path)
    yield conn
    conn.close()


def get_file_metadata(
    req: FileMetadataRequest,
    conn=Depends(get_db_connection),
) -> list[FileMetadata]:
    # TODO check permissions

    return get_all_metadata(conn, path_like=req.path_like)


router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/get_diff", response_model=DiffResponse)
def get_diff(
    req: DiffRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
    server_settings: ServerSettings = Depends(get_server_settings),
) -> DiffResponse:
    metadata_list = get_all_metadata(conn, path_like=f"{req.path}%")
    if len(metadata_list) == 0:
        raise HTTPException(status_code=404, detail="path not found")
    elif len(metadata_list) > 1:
        raise HTTPException(status_code=400, detail="too many files to get diff")

    metadata = metadata_list[0]
    abs_path = server_settings.snapshot_folder / metadata.path
    with open(abs_path, "rb") as f:
        data = f.read()

    # TODO load from cache
    diff = py_fast_rsync.diff(req.signature_bytes, data)
    diff_bytes = base64.b85encode(diff).decode("utf-8")
    return DiffResponse(
        path=metadata.path.as_posix(),
        diff=diff_bytes,
        hash=metadata.hash,
    )


@router.post("/dir_state", response_model=list[FileMetadata])
def dir_state(
    dir: Path,
    conn: sqlite3.Connection = Depends(get_db_connection),
    server_settings: ServerSettings = Depends(get_server_settings),
) -> list[FileMetadata]:
    if dir.is_absolute():
        raise HTTPException(status_code=400, detail="dir must be relative")

    result = get_all_metadata(conn, path_like=f"{dir.as_posix()}%")
    return result


@router.post("/get_metadata", response_model=list[FileMetadata])
def get_metadata(
    metadata: list[FileMetadata] = Depends(get_file_metadata),
) -> list[FileMetadata]:
    return metadata


@router.post("/apply_diff", response_model=ApplyDiffResponse)
def apply_diffs(
    req: ApplyDiffRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
    server_settings: ServerSettings = Depends(get_server_settings),
) -> ApplyDiffResponse:
    metadata_list = get_all_metadata(conn, path_like=f"{req.path}%")

    if len(metadata_list) == 0:
        raise HTTPException(status_code=404, detail="path not found")
    elif len(metadata_list) > 1:
        raise HTTPException(
            status_code=400, detail="found too many files to apply diff"
        )

    metadata = metadata_list[0]

    abs_path = server_settings.snapshot_folder / metadata.path
    with open(abs_path, "rb") as f:
        data = f.read()
    result = py_fast_rsync.apply(data, req.diff_bytes)
    sig = signature.calculate(result)
    sha256 = hashlib.sha256(result).hexdigest()
    if sha256 != req.expected_hash:
        raise HTTPException(status_code=400, detail="expected_hash mismatch")

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(result)
        temp_path = temp_file.name

    new_metadata = FileMetadata(
        path=temp_path,
        hash=sha256,
        signature=base64.b85encode(sig),
        file_size=len(data),
        last_modified=metadata.last_modified,
    )

    # move temp path to real path and update db
    move_with_transaction(
        conn,
        metadata=new_metadata,
        origin_path=abs_path,
    )

    return ApplyDiffResponse(
        path=req.path, current_hash=sha256, previous_hash=metadata.hash
    )
