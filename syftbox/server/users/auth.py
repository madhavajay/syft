import base64
import json
from typing_extensions import Annotated
from fastapi import Depends, HTTPException, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx

from syftbox.server.settings import ServerSettings, get_server_settings

bearer_scheme = HTTPBearer()

def validate_token(server_settings:ServerSettings, token: str) -> dict:
    if server_settings.no_auth:
        return json.loads(base64.b64decode(token).decode())
    else:
        raise NotImplementedError

def generate_token(server_settings:ServerSettings, email: str) -> str:
    # base64 encoding for testing purposes
    data = {"email": email}
    if server_settings.no_auth:
        return base64.b64encode(json.dumps(data).encode()).decode()
    else:
        raise NotImplementedError

def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme)],
    server_settings: Annotated[ServerSettings, Depends(get_server_settings)],
) -> str:
    try:
        data = validate_token(server_settings, credentials.credentials)
        return data['email']
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.reason_phrase,
            headers={"WWW-Authenticate": "Bearer"},
        )

