from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentUserDep, get_db_session, get_orchestrator
from api.schemas import (
    APIKeyResponse,
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from personal_assistant.auth.api_keys import generate_api_key
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.persistence.api_key_repository import APIKeyRepository
from personal_assistant.persistence.user_repository import UserRepository
from personal_assistant.persistence.user_workspace_repository import UserWorkspaceRepository
from personal_assistant.services.auth_service import AuthService, fork_default_workspace
from personal_assistant.services.exceptions import NotFoundError, ServiceValidationError

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


# ---------------------------------------------------------------------------
# API key management
# ---------------------------------------------------------------------------


def _api_key_response(row: object) -> APIKeyResponse:
    from personal_assistant.persistence.models import UserAPIKey

    assert isinstance(row, UserAPIKey)
    return APIKeyResponse(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        is_active=row.is_active,
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
        created_at=row.created_at,
    )


@router.post("/api-keys", response_model=CreateAPIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: CreateAPIKeyRequest,
    user: CurrentUserDep,
    session: DbSessionDep,
) -> CreateAPIKeyResponse:
    db = _require_session(session)
    raw_key, key_hash = generate_api_key()
    repo = APIKeyRepository(db)
    row = await repo.create(
        user_id=user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=raw_key[:11],
    )
    await db.commit()
    return CreateAPIKeyResponse(key=raw_key, api_key=_api_key_response(row))


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    user: CurrentUserDep,
    session: DbSessionDep,
) -> list[APIKeyResponse]:
    db = _require_session(session)
    repo = APIKeyRepository(db)
    rows = await repo.list_for_user(user.id)
    return [_api_key_response(r) for r in rows]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    user: CurrentUserDep,
    session: DbSessionDep,
) -> None:
    db = _require_session(session)
    repo = APIKeyRepository(db)
    revoked = await repo.revoke(user.id, key_id)
    if not revoked:
        raise NotFoundError("api_key", str(key_id))
    await db.commit()
