from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from api.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from personal_assistant.persistence.user_repository import UserRepository
from personal_assistant.services.auth_service import AuthService
from personal_assistant.services.exceptions import ServiceValidationError

router = APIRouter(prefix="/auth", tags=["auth"])

DbSessionDep = Annotated[AsyncSession | None, Depends(get_db_session)]


def _require_session(session: AsyncSession | None) -> AsyncSession:
    if session is None:
        raise ServiceValidationError("Database not configured. Set DATABASE_URL to enable auth.")
    return session


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: DbSessionDep) -> RegisterResponse:
    db = _require_session(session)
    service = AuthService(UserRepository(db))
    user, access_token, refresh_token = await service.register(
        username=body.username,
        email=body.email,
        password=body.password,
    )
    return RegisterResponse(
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
        ),
        tokens=TokenResponse(access_token=access_token, refresh_token=refresh_token),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: DbSessionDep) -> TokenResponse:
    db = _require_session(session)
    service = AuthService(UserRepository(db))
    _, access_token, refresh_token = await service.login(
        username=body.username, password=body.password
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, session: DbSessionDep) -> TokenResponse:
    db = _require_session(session)
    service = AuthService(UserRepository(db))
    new_access_token = await service.refresh(body.refresh_token)
    return TokenResponse(access_token=new_access_token, refresh_token=body.refresh_token)
