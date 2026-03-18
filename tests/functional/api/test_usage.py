"""Functional tests for /usage endpoints."""

from __future__ import annotations

import uuid

import httpx


async def _create_workspace(http_client_realdb: httpx.AsyncClient) -> str:
    workspace_name = f"usage-ws-{uuid.uuid4().hex[:8]}"
    response = await http_client_realdb.post(
        "/workspaces/",
        json={"name": workspace_name, "description": "Usage analytics test workspace"},
    )
    assert response.status_code == 201
    return workspace_name


async def _create_agent(
    http_client_realdb: httpx.AsyncClient,
    workspace_name: str,
    *,
    name: str,
    provider: str = "ollama",
    model: str = "llama3.2",
) -> None:
    response = await http_client_realdb.post(
        f"/workspaces/{workspace_name}/agents/",
        json={
            "name": name,
            "description": "Usage analytics test agent",
            "system_prompt": "You are a helpful test agent.",
            "provider": provider,
            "model": model,
        },
    )
    assert response.status_code == 201


async def _send_chat(
    http_client_realdb: httpx.AsyncClient, workspace_name: str, agent_name: str, message: str
) -> None:
    response = await http_client_realdb.post(
        f"/workspaces/{workspace_name}/agents/{agent_name}/chat",
        json={"message": message},
    )
    assert response.status_code == 200


async def test_usage_summary_aggregates_tokens_for_workspace(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    workspace_name = await _create_workspace(http_client_realdb)
    agent_name = f"UsageAgent{uuid.uuid4().hex[:6]}"
    await _create_agent(http_client_realdb, workspace_name, name=agent_name)

    await _send_chat(http_client_realdb, workspace_name, agent_name, "First usage test message.")
    await _send_chat(http_client_realdb, workspace_name, agent_name, "Second usage test message.")

    response = await http_client_realdb.get(
        "/usage/summary",
        params={"workspace": workspace_name, "period": "day"},
    )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 1
    assert all(row["workspace"] == workspace_name for row in rows)
    assert sum(row["prompt_tokens"] for row in rows) == 10
    assert sum(row["completion_tokens"] for row in rows) == 20
    assert sum(row["total_tokens"] for row in rows) == 30
    assert all(isinstance(row["estimated_cost_usd"], float) for row in rows)


async def test_usage_summary_provider_and_model_filters(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    workspace_name = await _create_workspace(http_client_realdb)
    agent_name = f"UsageAgent{uuid.uuid4().hex[:6]}"
    await _create_agent(http_client_realdb, workspace_name, name=agent_name)
    await _send_chat(http_client_realdb, workspace_name, agent_name, "Filter test message.")

    matching = await http_client_realdb.get(
        "/usage/summary",
        params={
            "workspace": workspace_name,
            "provider": "ollama",
            "model": "llama3.2",
            "period": "day",
        },
    )
    assert matching.status_code == 200
    assert len(matching.json()) >= 1

    non_matching = await http_client_realdb.get(
        "/usage/summary",
        params={
            "workspace": workspace_name,
            "provider": "ollama",
            "model": "model-does-not-exist",
            "period": "day",
        },
    )
    assert non_matching.status_code == 200
    assert non_matching.json() == []


async def test_usage_by_agent_filters_to_single_agent(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    workspace_name = await _create_workspace(http_client_realdb)
    primary_agent = f"UsageAgent{uuid.uuid4().hex[:6]}"
    secondary_agent = f"UsageAgent{uuid.uuid4().hex[:6]}"
    await _create_agent(http_client_realdb, workspace_name, name=primary_agent)
    await _create_agent(http_client_realdb, workspace_name, name=secondary_agent)

    await _send_chat(http_client_realdb, workspace_name, primary_agent, "Primary usage message 1.")
    await _send_chat(http_client_realdb, workspace_name, primary_agent, "Primary usage message 2.")
    await _send_chat(
        http_client_realdb, workspace_name, secondary_agent, "Secondary usage message."
    )

    response = await http_client_realdb.get(
        "/usage/by-agent",
        params={"workspace": workspace_name, "agent": primary_agent, "period": "day"},
    )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 1
    assert all(row["workspace"] == workspace_name for row in rows)
    assert all(row["agent_name"] == primary_agent for row in rows)
    for row in rows:
        uuid.UUID(row["agent_id"])
    assert sum(row["prompt_tokens"] for row in rows) == 10
    assert sum(row["completion_tokens"] for row in rows) == 20
    assert sum(row["total_tokens"] for row in rows) == 30


async def test_usage_by_agent_returns_empty_when_workspace_has_no_usage(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    workspace_name = await _create_workspace(http_client_realdb)
    response = await http_client_realdb.get(
        "/usage/by-agent",
        params={"workspace": workspace_name, "period": "day"},
    )

    assert response.status_code == 200
    assert response.json() == []
