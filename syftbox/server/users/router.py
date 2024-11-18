from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from syftbox.lib.email import send_token_email
from syftbox.server.settings import ServerSettings, get_server_settings
from syftbox.server.users.auth import generate_token, get_current_user

router = APIRouter(prefix="/auth", tags=["authentication"])


class TokenRequest(BaseModel):
    email: EmailStr

# Registration Flow
@router.post("/token")
def get_token(req: TokenRequest, server_settings: ServerSettings = Depends(get_server_settings)):
    email = req.email
    # Send email with token

    # for testing purposes, we will just return the token
    if server_settings.no_auth:
        token = generate_token(server_settings, email)
        send_token_email(email, token)
        return "Token Email sent succesfully! Check your email."
    else:
        return {"success": True}

@router.post("/validate")
def get_token(email: str = Depends(get_current_user)):
    return {"email": email}