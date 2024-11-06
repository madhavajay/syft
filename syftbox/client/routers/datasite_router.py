# routers/datasite_router.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from loguru import logger
from pydantic import BaseModel

router = APIRouter()


# Don't think we require this Request model until we have
# an endpoint that allows one to create a datasite
class DatasiteRequest(BaseModel):
    name: str


@router.get("/")
async def list_datasites(request: Request):
    """List all available datasites"""

    try:
        datasites = request.app.state.shared_state.get("my_datasites", [])
        return {"datasites": jsonable_encoder(datasites)}
    except Exception as e:
        logger.error(f"Error listing datasites: {e}")
        raise HTTPException(status_code=500, detail="Failed to list datasites")
