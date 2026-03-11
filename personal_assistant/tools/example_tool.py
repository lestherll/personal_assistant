from pydantic import BaseModel, Field

from ..core.tool import AssistantTool


class EchoInput(BaseModel):
    message: str = Field(description="The message to echo back.")


class EchoTool(AssistantTool):
    """Example tool — echoes the user's message back unchanged.

    Use this as a template when creating new tools:
    1. Define an `args_schema` Pydantic model for typed inputs.
    2. Set `name` and `description` so the agent knows when to use it.
    3. Implement `_run` with the actual logic.
    """

    name: str = "echo"
    description: str = (
        "Echoes the provided message back unchanged. "
        "Useful for testing that tool calls are wired up correctly."
    )
    args_schema: type[BaseModel] = EchoInput

    def _run(self, message: str) -> str:
        return message
