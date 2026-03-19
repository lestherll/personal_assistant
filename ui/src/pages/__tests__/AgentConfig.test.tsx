import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AgentConfig } from "../AgentConfig";
import * as clientModule from "../../api/client";

function wrapper(initialPath: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/workspaces/:name/agents/:agent" element={children} />
          <Route path="/workspaces/:name/agents/new" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AgentConfig — create mode", () => {
  it("shows validation when name is empty on submit", async () => {
    const { Wrapper } = { Wrapper: wrapper("/workspaces/test-ws/agents/new") };
    render(<AgentConfig />, { wrapper: Wrapper });

    const saveBtn = screen.getByRole("button", { name: /save agent/i });
    expect(saveBtn).toBeDisabled();
  });

  it("shows validation when system_prompt is empty", async () => {
    render(<AgentConfig />, { wrapper: wrapper("/workspaces/test-ws/agents/new") });

    // Name is the first textbox in the form
    fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "my-agent" } });
    const saveBtn = screen.getByRole("button", { name: /save agent/i });
    // Disabled because system_prompt is still empty
    expect(saveBtn).toBeDisabled();
  });
});

describe("AgentConfig — edit mode", () => {
  beforeEach(() => {
    vi.spyOn(clientModule.agents, "get").mockResolvedValue({
      config: {
        name: "existing-agent",
        description: "A test agent",
        system_prompt: "You are helpful.",
        provider: null,
        model: null,
        allowed_tools: null,
      },
      tools: [],
      llm_info: {},
    });
    vi.spyOn(clientModule.providers, "list").mockResolvedValue([]);
  });

  it("name field is disabled in edit mode", async () => {
    render(<AgentConfig />, {
      wrapper: wrapper("/workspaces/test-ws/agents/existing-agent"),
    });

    await waitFor(() => expect(screen.getByDisplayValue("existing-agent")).toBeInTheDocument());
    expect(screen.getByDisplayValue("existing-agent")).toBeDisabled();
  });

  it("pre-populates form from fetched agent config", async () => {
    render(<AgentConfig />, {
      wrapper: wrapper("/workspaces/test-ws/agents/existing-agent"),
    });

    await waitFor(() =>
      expect(screen.getByDisplayValue("You are helpful.")).toBeInTheDocument(),
    );
    expect(screen.getByDisplayValue("A test agent")).toBeInTheDocument();
  });
});
