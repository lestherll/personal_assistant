from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
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
from personal_assistant.config import get_settings
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.persistence.api_key_repository import APIKeyRepository
from personal_assistant.persistence.models import UserAPIKey
from personal_assistant.persistence.user_repository import UserRepository
from personal_assistant.persistence.user_workspace_repository import UserWorkspaceRepository
from personal_assistant.services.auth_service import AuthService, fork_default_workspace
from personal_assistant.services.exceptions import NotFoundError, ServiceValidationError

router = APIRouter(prefix="/auth", tags=["auth"])

DbSessionDep = Annotated[AsyncSession | None, Depends(get_db_session)]


def _set_auth_cookie(response: Response, access_token: str) -> None:
    """Set the httpOnly access_token cookie on a response.

    The cookie is SameSite=Lax which allows cross-site GET requests (e.g.
    navigating from an external link) while blocking cross-site POSTs (CSRF
    protection).  The ``secure`` flag is omitted here for local dev; set it
    via a production-specific override when serving over HTTPS.
    """
    settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def _require_session(session: AsyncSession | None) -> AsyncSession:
    if session is None:
        raise ServiceValidationError("Database not configured. Set DATABASE_URL to enable auth.")
    return session


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
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
    _set_auth_cookie(response, access_token)
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
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    response: Response,
    session: DbSessionDep,
) -> TokenResponse:
    db = _require_session(session)
    service = AuthService(UserRepository(db))
    _, access_token, refresh_token = await service.login(
        username=form.username, password=form.password
    )
    _set_auth_cookie(response, access_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest, response: Response, session: DbSessionDep
) -> TokenResponse:
    db = _require_session(session)
    service = AuthService(UserRepository(db))
    new_access_token = await service.refresh(body.refresh_token)
    _set_auth_cookie(response, new_access_token)
    return TokenResponse(access_token=new_access_token, refresh_token=body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    """Clear the httpOnly access_token cookie. No auth required."""
    response.delete_cookie(key="access_token", path="/")


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUserDep) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
# API key management
# ---------------------------------------------------------------------------


def _api_key_response(row: UserAPIKey) -> APIKeyResponse:
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


@router.post("/api-keys/{key_id}/rotate", response_model=CreateAPIKeyResponse)
async def rotate_api_key(
    key_id: uuid.UUID,
    user: CurrentUserDep,
    session: DbSessionDep,
) -> CreateAPIKeyResponse:
    db = _require_session(session)
    raw_key, key_hash = generate_api_key()
    repo = APIKeyRepository(db)
    row = await repo.rotate(
        user_id=user.id,
        key_id=key_id,
        new_key_hash=key_hash,
        new_key_prefix=raw_key[:11],
    )
    if row is None:
        raise NotFoundError("api_key", str(key_id))
    await db.commit()
    return CreateAPIKeyResponse(key=raw_key, api_key=_api_key_response(row))
