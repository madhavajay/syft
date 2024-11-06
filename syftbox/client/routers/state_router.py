# routers/state_router.py
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


class SharedStateRequest(BaseModel):
    key: str
    value: str


@router.get("/")
async def get_shared_state(request: Request):
    return JSONResponse(content=request.app.state.shared_state.data)


@router.post("/update")
async def update_shared_state(request: Request, state_req: SharedStateRequest):
    request.app.state.shared_state.update({state_req.key: state_req.value})
    return {"message": "State updated successfully"}


@router.get("/client_email")
async def get_config(request: Request):
    email = request.app.state.config.email
    return {"email": email}
