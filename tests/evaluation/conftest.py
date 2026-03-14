"""Evaluation test fixtures and LLM judge."""

from __future__ import annotations

import pytest
from deepeval.models import DeepEvalBaseLLM
from langchain_ollama import ChatOllama

JUDGE_MODEL = "qwen2.5:14b"


class OllamaJudge(DeepEvalBaseLLM):
    """DeepEval LLM judge backed by Ollama local model."""

    def get_model_name(self) -> str:
        return f"ollama/{JUDGE_MODEL}"

    def load_model(self) -> ChatOllama:
        return ChatOllama(model=JUDGE_MODEL, base_url="http://localhost:11434")

    def generate(self, prompt: str) -> str:
        response = self.load_model().invoke(prompt)
        return response.content

    async def a_generate(self, prompt: str) -> str:
        response = await self.load_model().ainvoke(prompt)
        return response.content


@pytest.fixture(scope="module")
def judge() -> OllamaJudge:
    """Ollama-backed DeepEval LLM judge."""
    return OllamaJudge()
