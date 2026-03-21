import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Chat } from "../Chat";
import * as clientModule from "../../api/client";

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof clientModule>("../../api/client");
  return {
    ...actual,
    workspaces: {
      ...actual.workspaces,
      get: vi.fn(),
    },
  };
});

// Mock useChatStream
vi.mock("../../hooks/useChatStream", () => ({
  useChatStream: () => ({
    messages: [],
    isStreaming: false,
    conversationId: null,
    error: null,
    send: vi.fn(),
    stop: vi.fn(),
    loadConversation: vi.fn(),
    clear: vi.fn(),
  }),
}));

const mockedWorkspaces = vi.mocked(clientModule.workspaces);

function Wrapper({
  initialPath,
  children,
}: {
  initialPath: string;
  children: React.ReactNode;
}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/workspaces/:name/chat" element={children} />
          <Route path="/workspaces/:name/chat/:convId" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => vi.clearAllMocks());

describe("Chat page", () => {
  it("shows 'no agents' empty state with create CTA when workspace has no agents", async () => {
    mockedWorkspaces.get.mockResolvedValue({
      name: "my-ws",
      agents: [],
      description: "",
      created_at: "",
      updated_at: "",
    });
    render(
      <Wrapper initialPath="/workspaces/my-ws/chat">
        <Chat />
      </Wrapper>
    );

    await waitFor(() =>
      expect(
        screen.getByText(/this workspace has no agents yet/i)
      ).toBeInTheDocument()
    );
    expect(
      screen.getByRole("button", { name: /create an agent/i })
    ).toBeInTheDocument();
  });

  it("shows agent selector when workspace has agents", async () => {
    mockedWorkspaces.get.mockResolvedValue({
      name: "my-ws",
      agents: [{ config: { name: "assistant", description: "", system_prompt: "" } }],
      description: "",
      created_at: "",
      updated_at: "",
    });
    render(
      <Wrapper initialPath="/workspaces/my-ws/chat">
        <Chat />
      </Wrapper>
    );

    await waitFor(() =>
      expect(screen.getByRole("option", { name: "Auto" })).toBeInTheDocument()
    );
    expect(screen.getByRole("option", { name: "assistant" })).toBeInTheDocument();
  });

  it("shows empty conversation prompt with agent name", async () => {
    mockedWorkspaces.get.mockResolvedValue({
      name: "my-ws",
      agents: [{ config: { name: "assistant", description: "", system_prompt: "" } }],
      description: "",
      created_at: "",
      updated_at: "",
    });
    render(
      <Wrapper initialPath="/workspaces/my-ws/chat">
        <Chat />
      </Wrapper>
    );

    await waitFor(() =>
      expect(screen.getByText(/start a conversation/i)).toBeInTheDocument()
    );
  });
});
