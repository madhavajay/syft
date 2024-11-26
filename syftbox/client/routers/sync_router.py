from typing import List

from fastapi import APIRouter, HTTPException
from loguru import logger

from syftbox.client.plugins.sync.local_state import LocalState, SyncStatusInfo
from syftbox.client.routers.common import APIContext

router = APIRouter()

# jinja_env = Environment(loader=FileSystemLoader("syftbox/assets/templates"))


# @router.get("/")
# def sync_dashboard():
#     template = jinja_env.get_template("sync_dashboard.jinja2")
#     return HTMLResponse(template.render())


@router.get("/data")
def get_sync_data(
    context: APIContext,
    order_by: str = "timestamp",
    order: str = "desc",
) -> List[SyncStatusInfo]:
    if order_by.lower() not in SyncStatusInfo.model_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order_by field: {order_by}. Available fields: {list(SyncStatusInfo.model_fields.keys())}",
        )
    if order.lower() not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail=f"Invalid order: {order}, expected 'asc' or 'desc'")

    sync_state = LocalState.for_client(context)
    if not sync_state.file_path.is_file():
        logger.error(f"LocalState file not found: {sync_state.file_path}")
        return []
    sync_state.load()
    logger.info(f"Loaded sync state: {sync_state.file_path}, with {len(sync_state.status_info)} entries")

    return sorted(
        sync_state.status_info.values(),
        key=lambda x: getattr(x, order_by),
        reverse=order.lower() == "desc",
    )
