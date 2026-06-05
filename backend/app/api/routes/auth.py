from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.core.auth import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
_limiter = Limiter(key_func=get_remote_address)


class Token(BaseModel):
    access_token: str
    token_type: str


@router.post("/token", response_model=Token)
@_limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    # SEC-06: rate limited to 10 requests/minute per IP to prevent brute-force
    if form_data.username != settings.api_username or not verify_password(
        form_data.password, settings.api_password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(form_data.username)
    return Token(access_token=token, token_type="bearer")
