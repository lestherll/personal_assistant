import asyncio
import os

from dotenv import load_dotenv

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.persistence.database import build_engine, build_session_factory
from personal_assistant.providers import (
    AnthropicProvider,
    OllamaConfig,
    OllamaProvider,
    ProviderRegistry,
)
from personal_assistant.workspaces.default_workspace import create_default_workspace


async def main() -> None:
    load_dotenv()

    # --- Provider registry ---
    registry = ProviderRegistry()
    registry.register(AnthropicProvider())
    registry.register(OllamaProvider(OllamaConfig(default_model="glm-5:cloud")), default=True)

    # --- Orchestrator + default workspace ---
    orchestrator = Orchestrator(registry)
    workspace = create_default_workspace(orchestrator)

    # --- Persistence (optional) ---
    database_url = os.getenv("DATABASE_URL")
    session_factory = None
    if database_url:
        engine = build_engine(database_url)
        session_factory = build_session_factory(engine)

    print("Personal Assistant")
    print(f"Providers : {registry.list()} (default: {registry.default})")
    print(f"Workspace : {workspace.config.name}")
    print(f"Agents    : {workspace.list_agents()}")
    print(f"Tools     : {workspace.list_tools()}")
    print(f"Database  : {'connected' if session_factory else 'not configured (in-memory only)'}")
    print("Type 'exit' to quit.\n")

    # --- Example: swap the assistant to a custom config at runtime ---
    # orchestrator.replace_agent(AgentConfig(
    #     name="Assistant",
    #     description="A snarky assistant.",
    #     system_prompt="You are a witty, sarcastic assistant. Keep replies short.",
    #     provider="ollama",
    #     model="glm-5",
    # ))

    while True:
        try:
            task = input("You: ").strip()
            if not task:
                continue
            if task.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            if session_factory:
                async with session_factory() as session:
                    response = await orchestrator.delegate(task, session=session)
            else:
                response = await orchestrator.delegate(task)

            print(f"\nAssistant: {response}\n")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    asyncio.run(main())
