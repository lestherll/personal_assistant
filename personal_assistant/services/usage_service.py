from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, Literal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from personal_assistant.persistence.models import Conversation, Message, UserAgent, UserWorkspace
from personal_assistant.services.exceptions import ServiceValidationError
from personal_assistant.services.views import UsageByAgentView, UsageSummaryView

UsagePeriod = Literal["day", "week", "month"]


@dataclass(frozen=True)
class TokenRate:
    prompt_per_1k: float
    completion_per_1k: float


_DEFAULT_PRICING: dict[tuple[str, str | None], TokenRate] = {
    ("anthropic", "claude-haiku-4-5-20251001"): TokenRate(
        prompt_per_1k=0.0008, completion_per_1k=0.004
    ),
    ("anthropic", "claude-sonnet-4-5"): TokenRate(prompt_per_1k=0.003, completion_per_1k=0.015),
    ("anthropic", "claude-opus-4-6"): TokenRate(prompt_per_1k=0.015, completion_per_1k=0.075),
    ("anthropic", None): TokenRate(prompt_per_1k=0.003, completion_per_1k=0.015),
    ("ollama", None): TokenRate(prompt_per_1k=0.0, completion_per_1k=0.0),
}


class UsageService:
    """Aggregate token usage and estimated cost for a user's data."""

    def __init__(self, pricing: dict[tuple[str, str | None], TokenRate] | None = None) -> None:
        self._pricing = pricing or _DEFAULT_PRICING

    async def get_usage_summary(
        self,
        user_id: uuid.UUID | None,
        session: AsyncSession,
        *,
        period: UsagePeriod = "day",
        workspace_name: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[UsageSummaryView]:
        self._validate_inputs(user_id, start=start, end=end)

        bind = session.get_bind()
        dialect = bind.dialect.name if bind is not None else "sqlite"
        period_expr = self._period_expression(period, dialect).label("period_start")
        prompt_sum = func.coalesce(func.sum(Message.prompt_tokens), 0).label("prompt_tokens")
        completion_sum = func.coalesce(func.sum(Message.completion_tokens), 0).label(
            "completion_tokens"
        )

        stmt = (
            select(
                UserWorkspace.name.label("workspace"),
                Message.provider,
                Message.model,
                period_expr,
                prompt_sum,
                completion_sum,
            )
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .join(UserWorkspace, Conversation.workspace_id == UserWorkspace.id)
            .where(UserWorkspace.user_id == user_id)
            .where(or_(Message.prompt_tokens.is_not(None), Message.completion_tokens.is_not(None)))
        )

        stmt = self._apply_filters(
            stmt,
            workspace_name=workspace_name,
            provider=provider,
            model=model,
            start=start,
            end=end,
        )

        stmt = stmt.group_by(
            UserWorkspace.name,
            Message.provider,
            Message.model,
            period_expr,
        ).order_by(period_expr, UserWorkspace.name)

        rows = await session.execute(stmt)
        return [self._row_to_summary(row) for row in rows]

    async def get_usage_by_agent(
        self,
        user_id: uuid.UUID | None,
        session: AsyncSession,
        *,
        period: UsagePeriod = "day",
        workspace_name: str | None = None,
        agent_name: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[UsageByAgentView]:
        self._validate_inputs(user_id, start=start, end=end)

        bind = session.get_bind()
        dialect = bind.dialect.name if bind is not None else "sqlite"
        period_expr = self._period_expression(period, dialect).label("period_start")
        prompt_sum = func.coalesce(func.sum(Message.prompt_tokens), 0).label("prompt_tokens")
        completion_sum = func.coalesce(func.sum(Message.completion_tokens), 0).label(
            "completion_tokens"
        )

        stmt = (
            select(
                UserWorkspace.name.label("workspace"),
                UserAgent.id.label("agent_id"),
                UserAgent.name.label("agent_name"),
                Message.provider,
                Message.model,
                period_expr,
                prompt_sum,
                completion_sum,
            )
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .join(UserWorkspace, Conversation.workspace_id == UserWorkspace.id)
            .join(UserAgent, Message.agent_id == UserAgent.id)
            .where(UserWorkspace.user_id == user_id)
            .where(or_(Message.prompt_tokens.is_not(None), Message.completion_tokens.is_not(None)))
        )

        if agent_name is not None:
            stmt = stmt.where(UserAgent.name == agent_name)

        stmt = self._apply_filters(
            stmt,
            workspace_name=workspace_name,
            provider=provider,
            model=model,
            start=start,
            end=end,
        )

        stmt = stmt.group_by(
            UserWorkspace.name,
            UserAgent.id,
            UserAgent.name,
            Message.provider,
            Message.model,
            period_expr,
        ).order_by(period_expr, UserWorkspace.name, UserAgent.name)

        rows = await session.execute(stmt)
        return [self._row_to_by_agent(row) for row in rows]

    def _apply_filters(
        self,
        stmt: Select[Any],
        *,
        workspace_name: str | None,
        provider: str | None,
        model: str | None,
        start: datetime | None,
        end: datetime | None,
    ) -> Select[Any]:
        if workspace_name is not None:
            stmt = stmt.where(UserWorkspace.name == workspace_name)
        if provider is not None:
            stmt = stmt.where(Message.provider == provider)
        if model is not None:
            stmt = stmt.where(Message.model == model)
        if start is not None:
            stmt = stmt.where(Message.created_at >= self._normalize_dt(start))
        if end is not None:
            stmt = stmt.where(Message.created_at <= self._normalize_dt(end))
        return stmt

    def _row_to_summary(self, row: Any) -> UsageSummaryView:
        prompt_tokens = int(row.prompt_tokens or 0)
        completion_tokens = int(row.completion_tokens or 0)
        total_tokens = prompt_tokens + completion_tokens
        cost = self._estimate_cost_usd(row.provider, row.model, prompt_tokens, completion_tokens)
        return UsageSummaryView(
            workspace=row.workspace,
            provider=row.provider,
            model=row.model,
            period_start=self._coerce_period_start(row.period_start),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
        )

    def _row_to_by_agent(self, row: Any) -> UsageByAgentView:
        prompt_tokens = int(row.prompt_tokens or 0)
        completion_tokens = int(row.completion_tokens or 0)
        total_tokens = prompt_tokens + completion_tokens
        cost = self._estimate_cost_usd(row.provider, row.model, prompt_tokens, completion_tokens)
        return UsageByAgentView(
            workspace=row.workspace,
            agent_id=row.agent_id,
            agent_name=row.agent_name,
            provider=row.provider,
            model=row.model,
            period_start=self._coerce_period_start(row.period_start),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
        )

    def _estimate_cost_usd(
        self,
        provider: str | None,
        model: str | None,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        if provider is None:
            return 0.0
        rate = self._pricing.get((provider, model)) or self._pricing.get((provider, None))
        if rate is None:
            return 0.0
        cost = (
            prompt_tokens * rate.prompt_per_1k + completion_tokens * rate.completion_per_1k
        ) / 1000
        return round(cost, 6)

    def _period_expression(self, period: UsagePeriod, dialect: str) -> ColumnElement[Any]:
        if dialect == "sqlite":
            if period == "day":
                return func.date(Message.created_at)
            if period == "week":
                return func.date(Message.created_at, "weekday 0", "-6 days")
            if period == "month":
                return func.strftime("%Y-%m-01", Message.created_at)
        return func.date_trunc(period, func.timezone("UTC", Message.created_at))

    def _coerce_period_start(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return self._normalize_dt(value)
        if isinstance(value, date):
            return datetime.combine(value, time.min, tzinfo=UTC)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            return self._normalize_dt(parsed)
        raise ServiceValidationError("Invalid period_start value")

    def _normalize_dt(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _validate_inputs(
        self,
        user_id: uuid.UUID | None,
        *,
        start: datetime | None,
        end: datetime | None,
    ) -> None:
        if user_id is None:
            raise ServiceValidationError("Usage analytics requires an authenticated user")
        if start is not None and end is not None:
            if self._normalize_dt(start) > self._normalize_dt(end):
                raise ServiceValidationError("start must be before end")
