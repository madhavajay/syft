# routers/datasite_router.py
from pathlib import Path

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from syftbox.client.routers.common import APIContext

router = APIRouter()


# Don't think we require this Request model until we have
# an endpoint that allows one to create a datasite
class DatasiteRequest(BaseModel):
    name: str


@router.get("/")
async def list_datasites(ctx: APIContext):
    """List all available datasites"""

    try:
        datasites_path: Path = ctx.workspace.datasites
        datasites = [p.name for p in datasites_path.glob("*") if ("@" in p and p.is_dir())]
        return {"datasites": datasites}
    except Exception as e:
        logger.error(f"Error listing datasites: {e}")
        raise HTTPException(status_code=500, detail="Failed to list datasites")
