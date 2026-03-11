from abc import abstractmethod
from typing import Any

from langchain_core.tools import BaseTool


class AssistantTool(BaseTool):
    """Base class for all personal assistant tools.

    Subclass this and implement `_run` to create a new tool.
    Set `name`, `description`, and optionally `args_schema` (a Pydantic model).
    """

    @abstractmethod
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool synchronously."""
        ...

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool asynchronously (delegates to sync by default)."""
        return self._run(*args, **kwargs)
