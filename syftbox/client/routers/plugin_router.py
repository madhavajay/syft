import time
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel

router = APIRouter()
current_dir = Path(__file__).parent.parent

templates = Jinja2Templates(directory=str(current_dir / "templates"))


class PluginRequest(BaseModel):
    plugin_name: str


def run_plugin(plugin_name, loaded_plugins, shared_state, *args, **kwargs):
    try:
        module = loaded_plugins[plugin_name].module
        module.run(shared_state, *args, **kwargs)
    except Exception as e:
        logger.exception(e)


def start_plugin(app: FastAPI, plugin_name: str):
    if "sync" in plugin_name:
        return {"message": "Sync plugins cannot be started manually"}

    if plugin_name not in app.state.loaded_plugins:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin {plugin_name} is not loaded",
        )

    if plugin_name in app.state.running_plugins:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin {plugin_name} is already running",
        )

    try:
        plugin = app.state.loaded_plugins[plugin_name]

        existing_job = app.state.scheduler.get_job(plugin_name)
        if existing_job is None:
            job = app.state.scheduler.add_job(
                func=run_plugin,
                trigger="interval",
                seconds=plugin.schedule / 1000,
                id=plugin_name,
                args=[plugin_name, app.state.loaded_plugins, app.state.shared_state],
            )
            app.state.running_plugins[plugin_name] = {
                "job": job,
                "start_time": time.time(),
                "schedule": plugin.schedule,
            }
            return {"message": f"Plugin {plugin_name} started successfully"}
        else:
            logger.info(f"Job {existing_job}, already added")
            return {"message": f"Plugin {plugin_name} already started"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start plugin {plugin_name}: {e}",
        )


@router.get("/", response_class=HTMLResponse)
async def plugin_manager(request: Request):
    # Pass the request to the template to allow FastAPI to render it
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/launch")
async def start_plugin_endpoint(request: Request, plugin_req: PluginRequest):
    return start_plugin(request.app, plugin_req.plugin_name)


@router.post("/kill")
async def stop_plugin(request: Request, plugin_req: PluginRequest):
    if plugin_req.plugin_name not in request.app.state.running_plugins:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin {plugin_req.plugin_name} is not running",
        )

    try:
        request.app.state.scheduler.remove_job(plugin_req.plugin_name)
        del request.app.state.running_plugins[plugin_req.plugin_name]
        return {"message": f"Plugin {plugin_req.plugin_name} stopped successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop plugin {plugin_req.plugin_name}: {str(e)}",
        )


@router.get("/plugins")
async def list_plugins(request: Request):
    plugins = []
    for name, plugin in request.app.state.loaded_plugins.items():
        plugin = {
            "name": name,
            "description": plugin.description,
            "schedule": plugin.schedule,
            "running": name in request.app.state.running_plugins,
        }
        plugins.append(plugin)
    return {"plugins": plugins}


@router.get("/running")
def list_running_plugins(request: Request):
    running = {
        name: {
            "is_running": data["job"].next_run_time is not None,
            "run_time": time.time() - data["start_time"],
            "schedule": data["schedule"],
        }
        for name, data in request.app.state.running_plugins.items()
    }
    return {"running_plugins": running}
