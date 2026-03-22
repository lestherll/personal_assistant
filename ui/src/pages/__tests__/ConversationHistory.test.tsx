import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConversationHistory } from "../ConversationHistory";
import * as clientModule from "../../api/client";

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof clientModule>("../../api/client");
  return {
    ...actual,
    workspaces: {
      ...actual.workspaces,
      listConversations: vi.fn(),
      getMessages: vi.fn(),
      deleteConversation: vi.fn(),
    },
  };
});

const mockedWorkspaces = vi.mocked(clientModule.workspaces);

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/workspaces/my-ws/history"]}>
        <Routes>
          <Route path="/workspaces/:name/history" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const CONVERSATIONS = [
  {
    id: "conv-1",
    title: "First Chat",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "conv-2",
    title: "Second Chat",
    created_at: "2024-01-02T00:00:00Z",
    updated_at: "2024-01-02T00:00:00Z",
  },
];

beforeEach(() => vi.clearAllMocks());

describe("ConversationHistory page", () => {
  it("renders conversation list", async () => {
    mockedWorkspaces.listConversations.mockResolvedValue(CONVERSATIONS);
    render(<ConversationHistory />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByText("First Chat")).toBeInTheDocument()
    );
    expect(screen.getByText("Second Chat")).toBeInTheDocument();
  });

  it("shows empty state when no conversations", async () => {
    mockedWorkspaces.listConversations.mockResolvedValue([]);
    render(<ConversationHistory />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByText(/no conversations here yet/i)).toBeInTheDocument()
    );
  });

  it("renders a delete button for each conversation", async () => {
    mockedWorkspaces.listConversations.mockResolvedValue(CONVERSATIONS);
    render(<ConversationHistory />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByText("First Chat")).toBeInTheDocument()
    );

    const deleteButtons = screen.getAllByRole("button", {
      name: /delete conversation/i,
    });
    expect(deleteButtons).toHaveLength(2);
  });

  it("calls deleteConversation and deselects when deleting selected conversation", async () => {
    mockedWorkspaces.listConversations.mockResolvedValue(CONVERSATIONS);
    mockedWorkspaces.getMessages.mockResolvedValue([]);
    mockedWorkspaces.deleteConversation.mockResolvedValue(undefined);

    render(<ConversationHistory />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByText("First Chat")).toBeInTheDocument()
    );

    // Select first conversation
    fireEvent.click(screen.getByText("First Chat"));

    // Delete first conversation
    const deleteButtons = screen.getAllByRole("button", {
      name: /delete conversation/i,
    });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() =>
      expect(mockedWorkspaces.deleteConversation).toHaveBeenCalledWith(
        "my-ws",
        "conv-1"
      )
    );
  });

  it("calls deleteConversation for the correct id", async () => {
    mockedWorkspaces.listConversations.mockResolvedValue(CONVERSATIONS);
    mockedWorkspaces.deleteConversation.mockResolvedValue(undefined);

    render(<ConversationHistory />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByText("Second Chat")).toBeInTheDocument()
    );

    const deleteButtons = screen.getAllByRole("button", {
      name: /delete conversation/i,
    });
    fireEvent.click(deleteButtons[1]);

    await waitFor(() =>
      expect(mockedWorkspaces.deleteConversation).toHaveBeenCalledWith(
        "my-ws",
        "conv-2"
      )
    );
  });
});
