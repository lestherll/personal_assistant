from dotenv import load_dotenv

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.providers import (
    AnthropicProvider,
    OllamaConfig,
    OllamaProvider,
    ProviderRegistry,
)
from personal_assistant.workspaces.default_workspace import create_default_workspace


def main() -> None:
    load_dotenv()

    # --- Provider registry ---
    registry = ProviderRegistry()
    registry.register(AnthropicProvider())
    registry.register(OllamaProvider(OllamaConfig(default_model="qwen3:8b")), default=True)

    # --- Orchestrator + default workspace ---
    orchestrator = Orchestrator(registry)
    workspace = create_default_workspace(orchestrator)

    print("Personal Assistant")
    print(f"Providers : {registry.list()} (default: {registry.default})")
    print(f"Workspace : {workspace.config.name}")
    print(f"Agents    : {workspace.list_agents()}")
    print(f"Tools     : {workspace.list_tools()}")
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
            response = orchestrator.delegate(task)
            print(f"\nAssistant: {response}\n")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
