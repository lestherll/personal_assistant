from __future__ import annotations

from typing import Annotated

from fastapi import Path

WorkspaceName = Annotated[
    str, Path(openapi_examples={"default": {"value": "default", "summary": "Default workspace"}})
]
AgentName = Annotated[
    str,
    Path(openapi_examples={"assistant": {"value": "Assistant", "summary": "General assistant"}}),
]
