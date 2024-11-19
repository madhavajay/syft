import base64
from datetime import datetime, timezone
import json
from typing_extensions import Annotated
from fastapi import Depends, HTTPException, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx
import jwt
from syftbox.server.settings import ServerSettings, get_server_settings

bearer_scheme = HTTPBearer()


def _validate_jwt(server_settings: ServerSettings, token: str) -> dict:
    try:
        return jwt.decode(
            token,
            server_settings.jwt_secret.get_secret_value(),
            algorithms=[server_settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def _generate_jwt(server_settings: ServerSettings, data: dict) -> str:
    if server_settings.jwt_expiration is not None:
        data["exp"] = datetime.now(tz=timezone.utc) + server_settings.jwt_expiration

    return jwt.encode(
        data,
        server_settings.jwt_secret.get_secret_value(),
        algorithm=server_settings.jwt_algorithm,
    )


def generate_token(server_settings: ServerSettings, data: json) -> str:
    """
    payload looks like:
    {email: x, iat: date, type: access_token, exp: date}

    If no auth, the token is a base64 encoded json string.
    If auth, the token is a jwt token.

    Args:
        server_settings (ServerSettings): server settings
        data (json): data to encode

    Returns:
        str: _description_
    """
    if not server_settings.auth_enabled:
        return base64.b64encode(json.dumps(data).encode()).decode()
    else:
        return _generate_jwt(server_settings, data)


def validate_token(server_settings: ServerSettings, token: str) -> dict:
    """
    payload looks like:
    {email: x, iat: date, type: access_token, exp: date}

    If no auth, the token is a base64 encoded json string.
    If auth, the token is a jwt token.

    Args:
        server_settings (ServerSettings): server settings
        token (str): token to decode

    Returns:
        dict: decoded payload
    """
    if not server_settings.auth_enabled:
        return json.loads(base64.b64decode(token).decode())
    else:
        return _validate_jwt(server_settings, token)


def generate_access_token(server_settings: ServerSettings, email: str) -> str:
    data = {"email": email, "type": "access_token"}
    return generate_token(server_settings, data)


def generate_email_token(server_settings: ServerSettings, email: str) -> str:
    data = {"email": email, "type": "email_token"}
    return generate_token(server_settings, data)


def get_user_from_email_token(
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

