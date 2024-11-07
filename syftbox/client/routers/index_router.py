from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from loguru import logger

from syftbox import __version__
from syftbox.client.routers.common import APIContext
from syftbox.lib.debug import debug_report

router = APIRouter()


@router.get("/")
async def index():
    return PlainTextResponse(f"SyftBox {__version__}")


@router.get("/version")
async def version():
    return {"version": __version__}


@router.get("/report")
async def report(ctx: APIContext):
    try:
        return debug_report(ctx.config.path)
    except Exception as e:
        logger.exception("Error generating report", e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error generating report",
                "message": str(e),
            },
        )
