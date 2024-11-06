# routers/file_router.py
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()


# AFAIK: This API is currently not used, not sure if it will be used in the future
# I think we can think of depreciating this API if there is no clear use case for it
@router.post("/operation")
async def file_operation(request: Request):
    """Handle file operations"""
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse request data: {e!s}",
        )

    operation = data.get("operation")
    file_path = data.get("file_path")

    if not file_path:
        raise HTTPException(status_code=400, detail="Path is required")

    full_path = Path(request.app.state.shared_state.client_config.sync_folder) / file_path

    # Ensure the path is within the SyftBox directory
    if not full_path.resolve().is_relative_to(
        Path(request.app.state.shared_state.client_config.sync_folder),
    ):
        raise HTTPException(
            status_code=403,
            detail="Access to files outside SyftBox directory is not allowed",
        )

    if operation == "read":
        if not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(full_path)

    if operation in ["write", "append"]:
        content = data.get("content", None)
        if content is None:
            raise HTTPException(
                status_code=400,
                detail="Content is required for write or append operation",
            )

        # Ensure the directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            mode = "w" if operation == "write" else "a"
            with open(full_path, mode) as f:
                f.write(content)
            return JSONResponse(content={"message": f"File {operation}ed successfully"})
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to {operation} file: {e!s}",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid operation. Use 'read', 'write', or 'append'",
        )
