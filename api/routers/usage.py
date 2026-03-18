from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentUserDep, get_db_session, get_usage_service
from api.schemas import UsageByAgentResponse, UsageSummaryResponse
from personal_assistant.services.usage_service import UsagePeriod, UsageService

router = APIRouter(prefix="/usage", tags=["usage"])

UsageServiceDep = Annotated[UsageService, Depends(get_usage_service)]
DbSessionDep = Annotated[AsyncSession | None, Depends(get_db_session)]

UsagePeriodParam = Annotated[
    UsagePeriod,
    Query(
        description="Aggregation period.",
        openapi_examples={"default": {"value": "day", "summary": "Daily buckets"}},
    ),
]


@router.get("/summary", response_model=list[UsageSummaryResponse])
async def usage_summary(
    service: UsageServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    period: UsagePeriodParam = "day",
    workspace: Annotated[str | None, Query(description="Workspace name filter.")] = None,
    provider: Annotated[str | None, Query(description="Provider filter.")] = None,
    model: Annotated[str | None, Query(description="Model filter.")] = None,
    start: Annotated[datetime | None, Query(description="Start time (inclusive).")] = None,
    end: Annotated[datetime | None, Query(description="End time (inclusive).")] = None,
) -> list[UsageSummaryResponse]:
    if db is None:
        return []
    views = await service.get_usage_summary(
        current_user.id,
        db,
        period=period,
        workspace_name=workspace,
        provider=provider,
        model=model,
        start=start,
        end=end,
    )
    return [UsageSummaryResponse.from_view(v) for v in views]


@router.get("/by-agent", response_model=list[UsageByAgentResponse])
async def usage_by_agent(
    service: UsageServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    period: UsagePeriodParam = "day",
    workspace: Annotated[str | None, Query(description="Workspace name filter.")] = None,
    agent: Annotated[str | None, Query(description="Agent name filter.")] = None,
    provider: Annotated[str | None, Query(description="Provider filter.")] = None,
    model: Annotated[str | None, Query(description="Model filter.")] = None,
    start: Annotated[datetime | None, Query(description="Start time (inclusive).")] = None,
    end: Annotated[datetime | None, Query(description="End time (inclusive).")] = None,
) -> list[UsageByAgentResponse]:
    if db is None:
        return []
    views = await service.get_usage_by_agent(
        current_user.id,
        db,
        period=period,
        workspace_name=workspace,
        agent_name=agent,
        provider=provider,
        model=model,
        start=start,
        end=end,
    )
    return [UsageByAgentResponse.from_view(v) for v in views]
