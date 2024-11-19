from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
import shutil

from syftbox.lib.email import send_token_email, send_token_reset_password
from syftbox.server.settings import ServerSettings, get_server_settings
from syftbox.server.users.auth import generate_access_token, generate_password_reset_token, get_current_user, validate_token
from syftbox.server.users.db import add_user, get_user_by_email, update_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


class TokenRequest(BaseModel):
    email: EmailStr

# Registration Flow
@router.post("/token")
def get_token(req: TokenRequest, server_settings: ServerSettings = Depends(get_server_settings)):
    email = req.email
    # Send email with token
    if server_settings.no_auth:
        token = generate_access_token(server_settings, email)
        send_token_email(email, token)
        return "Token Email sent succesfully! Check your email."
    else:
        return {"success": True}
    

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register_user(req: RegisterRequest, server_settings: ServerSettings = Depends(get_server_settings)):
    email = req.email
    user = get_user_by_email(email)
    if user:
        raise HTTPException(status_code=400, detail="Email already exists")
    add_user(req.password, email)
    token = generate_access_token(server_settings, email)
    send_token_email(email, token)
    return "Token Email sent succesfully! Check your email."


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/login")
def login_user(req: LoginRequest, server_settings: ServerSettings = Depends(get_server_settings)):
    email = req.email
    user = get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    if verify_password(req.password, user):
        token = generate_access_token(server_settings, email)
        return token
    raise HTTPException(status_code=401, detail="Passwords do not match!")


class ResetPasswordRequest(BaseModel):
    email: EmailStr

@router.post("/reset_password")
def request_password_reset(req: ResetPasswordRequest, server_settings: ServerSettings = Depends(get_server_settings)):
    email = req.email
    user = get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    # generate token for password reset
    token = generate_password_reset_token(server_settings=server_settings, email=email)
    # send reset password email with the token
    send_token_reset_password(email, token)
    return f"Token sent to {email}"

class ChangePasswordRequest(BaseModel):
    email: EmailStr
    token: str
    new_password: str
    
@router.post("/change_password")
def change_password(req: ChangePasswordRequest, server_settings: ServerSettings = Depends(get_server_settings)):
    email = req.email
    user = get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    
    # validate password reset token
    data = validate_token(server_settings, req.token)
    if email == data.get('email', None) and data.get('reset_password', False):
        # change password
        update_password(email, req.new_password)
        return "Password updated succesfully!"
    raise HTTPException(status_code=401, detail="Invalid Token")


class BanRequest(BaseModel):
    email: EmailStr
    
@router.post("/ban")
def ban(req: BanRequest, server_settings: ServerSettings = Depends(get_server_settings)):
    email = req.email
    user = get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    if user.is_banned:
        raise HTTPException(status_code=400, detail="User already banned")
    ban(email)
    # Delete files
    user_folder_path = server_settings.snapshot_folder / email
    shutil.rmtree(user_folder_path) 
    return f"User {email} banned succesfully" 


class UnBanRequest(BaseModel):
    email: EmailStr
    
@router.post("/unban")
def unban(req: UnBanRequest, server_settings: ServerSettings = Depends(get_server_settings)):
    email = req.email
    user = get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    if not user.is_banned:
        raise HTTPException(status_code=400, detail="User not banned")
    unban(email)
    return f"User {email} unbanned succesfully"


@router.post("/validate")
def get_token(email: str = Depends(get_current_user)):
    return {"email": email}