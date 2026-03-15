"""Tests for the stateless route() function in supervisor.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from personal_assistant.core.supervisor import AgentInfo, route


def _make_llm(chosen: str) -> MagicMock:
    """Return a mock LLM whose structured-output chain returns *chosen*."""
    decision = MagicMock()
    decision.next_agent = chosen

    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=decision)

    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=chain)
    return llm


AGENTS = [
    AgentInfo(name="coding", description="Helps with coding tasks"),
    AgentInfo(name="research", description="Helps with research tasks"),
    AgentInfo(name="career", description="Helps with career tasks"),
]


class TestRoute:
    async def test_returns_valid_agent_name(self):
        llm = _make_llm("research")
        result = await route("Summarise this paper", AGENTS, llm)
        assert result == "research"

    async def test_first_agent_is_fallback(self):
        """When the LLM returns an unknown name, fall back to the first agent."""
        llm = _make_llm("unknown_agent")
        result = await route("some message", AGENTS, llm)
        assert result == AGENTS[0].name

    async def test_empty_next_agent_falls_back(self):
        llm = _make_llm("")
        result = await route("some message", AGENTS, llm)
        assert result == AGENTS[0].name

    async def test_calls_with_structured_output(self):
        llm = _make_llm("coding")
        await route("write a function", AGENTS, llm)
        llm.with_structured_output.assert_called_once()

    async def test_ainvoke_receives_system_and_human_messages(self):
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = _make_llm("coding")
        await route("write a function", AGENTS, llm)

        chain = llm.with_structured_output.return_value
        call_args = chain.ainvoke.call_args
        messages = call_args[0][0]

        assert any(isinstance(m, SystemMessage) for m in messages)
        assert any(isinstance(m, HumanMessage) for m in messages)

    async def test_human_message_contains_user_message(self):
        from langchain_core.messages import HumanMessage

        llm = _make_llm("coding")
        await route("write a sorting algorithm", AGENTS, llm)

        chain = llm.with_structured_output.return_value
        messages = chain.ainvoke.call_args[0][0]
        human_msgs = [m for m in messages if isinstance(m, HumanMessage)]

        assert len(human_msgs) == 1
        assert "write a sorting algorithm" in human_msgs[0].content

    async def test_system_message_lists_agent_names(self):
        from langchain_core.messages import SystemMessage

        llm = _make_llm("career")
        await route("help with my resume", AGENTS, llm)

        chain = llm.with_structured_output.return_value
        messages = chain.ainvoke.call_args[0][0]
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]

        assert len(system_msgs) == 1
        for agent in AGENTS:
            assert agent.name in system_msgs[0].content

    async def test_single_agent_list(self):
        agents = [AgentInfo(name="solo", description="Only agent")]
        llm = _make_llm("solo")
        result = await route("anything", agents, llm)
        assert result == "solo"

    async def test_single_agent_fallback(self):
        """With one agent, even a bad LLM response falls back correctly."""
        agents = [AgentInfo(name="solo", description="Only agent")]
        llm = _make_llm("bad_name")
        result = await route("anything", agents, llm)
        assert result == "solo"
