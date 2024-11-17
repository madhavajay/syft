from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

router = APIRouter()

jinja_env = Environment(loader=FileSystemLoader("syftbox/assets/templates"))


@router.get("/")
def sync_dashboard():
    print(jinja_env.list_templates())
    template = jinja_env.get_template("sync_dashboard.jinja2")
    return HTMLResponse(template.render())
