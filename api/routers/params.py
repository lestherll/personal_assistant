from __future__ import annotations

from typing import Annotated

from fastapi import Path, Query

WorkspaceName = Annotated[
    str, Path(openapi_examples={"default": {"value": "default", "summary": "Default workspace"}})
]
AgentName = Annotated[
    str,
    Path(openapi_examples={"assistant": {"value": "Assistant", "summary": "General assistant"}}),
]

PaginationSkip = Annotated[
    int,
    Query(
        ge=0,
        description="Number of records to skip before returning results.",
        openapi_examples={"default": {"value": 0, "summary": "First page offset"}},
    ),
]
PaginationLimit = Annotated[
    int,
    Query(
        ge=1,
        description="Maximum number of records to return.",
        openapi_examples={"default": {"value": 50, "summary": "Default page size"}},
    ),
]
