import base64
import sqlite3
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import py_fast_rsync
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from loguru import logger

from syftbox.lib.lib import PermissionTree, SyftPermission, filter_metadata
from syftbox.server.settings import ServerSettings, get_server_settings
from syftbox.server.sync.db import (
    get_all_datasites,
    get_all_metadata,
    get_db,
    move_with_transaction,
    save_file_metadata,
)
from syftbox.server.sync.file_store import FileStore
from syftbox.server.sync.hash import hash_file

from .models import (
    ApplyDiffRequest,
    ApplyDiffResponse,
    BatchFileRequest,
    DiffRequest,
    DiffResponse,
    FileMetadata,
    FileMetadataRequest,
    FileRequest,
)


def get_db_connection(request: Request):
    conn = get_db(request.state.server_settings.file_db_path)
    yield conn
    conn.close()


def get_file_store(request: Request):
    store = FileStore(
        server_settings=request.state.server_settings,
    )
    yield store


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
    file_store: FileStore = Depends(get_file_store),
) -> DiffResponse:
    try:
        file = file_store.get(req.path)
    except ValueError:
        raise HTTPException(status_code=404, detail="file not found")
    diff = py_fast_rsync.diff(req.signature_bytes, file.data)
    diff_bytes = base64.b85encode(diff).decode("utf-8")
    return DiffResponse(
        path=file.metadata.path.as_posix(),
        diff=diff_bytes,
        hash=file.metadata.hash,
    )


@router.post("/dir_state", response_model=list[FileMetadata])
def dir_state(
    dir: Path,
    conn: sqlite3.Connection = Depends(get_db_connection),
    server_settings: ServerSettings = Depends(get_server_settings),
    email: str = Header(),
) -> list[FileMetadata]:
    if dir.is_absolute():
        raise HTTPException(status_code=400, detail="dir must be relative")

    metadata = get_all_metadata(conn, path_like=f"{dir.as_posix()}%")
    full_path = server_settings.snapshot_folder / dir
    # get the top level perm file
    try:
        perm_tree = PermissionTree.from_path(full_path, raise_on_corrupted_files=True)
    except Exception as e:
        print(f"Failed to parse permission tree: {dir}")
        raise e

    # filter the read state for this user by the perm tree
    filtered_metadata = filter_metadata(email, metadata, perm_tree, server_settings.snapshot_folder)
    return filtered_metadata


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
    metadata_list = get_all_metadata(conn, path_like=f"{req.path}")

    if len(metadata_list) == 0:
        raise HTTPException(status_code=404, detail="path not found")
    elif len(metadata_list) > 1:
        raise HTTPException(status_code=400, detail="found too many files to apply diff")

    metadata = metadata_list[0]

    abs_path = server_settings.snapshot_folder / metadata.path
    with open(abs_path, "rb") as f:
        data = f.read()
    result = py_fast_rsync.apply(data, req.diff_bytes)

    if SyftPermission.is_permission_file(metadata.path) and not SyftPermission.is_valid(result):
        raise HTTPException(status_code=400, detail="invalid syftpermission contents, skipped writing")

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(result)
        temp_path = Path(temp_file.name)

    new_metadata = hash_file(temp_path)

    if new_metadata.hash != req.expected_hash:
        raise HTTPException(status_code=400, detail="expected_hash mismatch")

    # move temp path to real path and update db
    move_with_transaction(
        conn,
        metadata=new_metadata,
        origin_path=abs_path,
        server_settings=server_settings,
    )

    return ApplyDiffResponse(path=req.path, current_hash=new_metadata.hash, previous_hash=metadata.hash)


@router.post("/delete", response_class=JSONResponse)
def delete_file(
    req: FileRequest,
    file_store: FileStore = Depends(get_file_store),
) -> JSONResponse:
    file_store.delete(req.path)
    return JSONResponse(content={"status": "success"})


@router.post("/create", response_class=JSONResponse)
def create_file(
    file: UploadFile,
    conn: sqlite3.Connection = Depends(get_db_connection),
    server_settings: ServerSettings = Depends(get_server_settings),
) -> JSONResponse:
    #
    relative_path = Path(file.filename)
    abs_path = server_settings.snapshot_folder / relative_path

    contents = file.file.read()

    if SyftPermission.is_permission_file(relative_path) and not SyftPermission.is_valid(contents):
        raise HTTPException(status_code=400, detail="invalid syftpermission contents, skipped writing")

    abs_path.parent.mkdir(exist_ok=True, parents=True)

    with open(abs_path, "wb") as f:
        # better to use async aiosqlite
        f.write(contents)

    cursor = conn.cursor()
    metadata = get_all_metadata(cursor, path_like=f"{file.filename}")
    if len(metadata) > 0:
        raise HTTPException(status_code=400, detail="file already exists")
    metadata = hash_file(abs_path, root_dir=server_settings.snapshot_folder)
    save_file_metadata(cursor, metadata)
    conn.commit()
    cursor.close()

    return JSONResponse(content={"status": "success"})


@router.post("/download", response_class=FileResponse)
def download_file(
    req: FileRequest,
    file_store: FileStore = Depends(get_file_store),
) -> FileResponse:
    try:
        abs_path = file_store.get(req.path).absolute_path
        return FileResponse(abs_path)
    except ValueError:
        raise HTTPException(status_code=404, detail="file not found")


@router.post("/datasites", response_model=list[str])
def get_datasites(conn: sqlite3.Connection = Depends(get_db_connection)) -> list[str]:
    return get_all_datasites(conn)


def create_zip_from_files(file_metadatas: list[FileMetadata], server_settings: ServerSettings) -> BytesIO:
    file_paths = [server_settings.snapshot_folder / file_metadata.path for file_metadata in file_metadatas]
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, "w") as zf:
        for file_path in file_paths:
            with open(file_path, "rb") as file:
                zf.writestr(file_path.relative_to(server_settings.snapshot_folder).as_posix(), file.read())
    memory_file.seek(0)
    return memory_file


@router.post("/download_bulk")
async def get_files(
    req: BatchFileRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
    server_settings: ServerSettings = Depends(get_server_settings),
) -> StreamingResponse:
    all_metadata = []
    for path in req.paths:
        metadata_list = get_all_metadata(conn, path_like=f"{path}")
        if len(metadata_list) != 1:
            logger.warning(f"Expected 1 metadata, got {len(metadata_list)} for {path}")
            continue
        metadata = metadata_list[0]
        abs_path = server_settings.snapshot_folder / metadata.path
        if not Path(abs_path).exists() or not Path(abs_path).is_file():
            logger.warning(f"File not found: {abs_path}")
            continue
        all_metadata.append(metadata)
    zip_file = create_zip_from_files(all_metadata, server_settings)
    return Response(content=zip_file.read(), media_type="application/zip")
