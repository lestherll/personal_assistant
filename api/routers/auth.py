from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session, get_orchestrator
from api.schemas import (
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.persistence.user_repository import UserRepository
from personal_assistant.persistence.user_workspace_repository import UserWorkspaceRepository
from personal_assistant.services.auth_service import AuthService, fork_default_workspace
from personal_assistant.services.exceptions import ServiceValidationError

router = APIRouter(prefix="/auth", tags=["auth"])

DbSessionDep = Annotated[AsyncSession | None, Depends(get_db_session)]


def _require_session(session: AsyncSession | None) -> AsyncSession:
    if session is None:
        raise ServiceValidationError("Database not configured. Set DATABASE_URL to enable auth.")
    return session


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    session: DbSessionDep,
) -> RegisterResponse:
    db = _require_session(session)
    service = AuthService(UserRepository(db))
    user, access_token, refresh_token = await service.register(
        username=body.username,
        email=body.email,
        password=body.password,
    )
    orchestrator: Orchestrator = get_orchestrator(request)
    await fork_default_workspace(
        user_id=user.id,
        default_orchestrator=orchestrator,
        user_workspace_repo=UserWorkspaceRepository(db),
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
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], session: DbSessionDep
) -> TokenResponse:
    db = _require_session(session)
    service = AuthService(UserRepository(db))
    _, access_token, refresh_token = await service.login(
        username=form.username, password=form.password
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, session: DbSessionDep) -> TokenResponse:
    db = _require_session(session)
    service = AuthService(UserRepository(db))
    new_access_token = await service.refresh(body.refresh_token)
    return TokenResponse(access_token=new_access_token, refresh_token=body.refresh_token)
