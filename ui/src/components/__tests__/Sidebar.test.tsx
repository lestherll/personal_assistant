import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Sidebar } from "../Sidebar";
import * as clientModule from "../../api/client";

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof clientModule>("../../api/client");
  return {
    ...actual,
    workspaces: {
      ...actual.workspaces,
      list: vi.fn(),
      listConversations: vi.fn(),
      deleteConversation: vi.fn(),
    },
  };
});

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({ user: { username: "testuser" }, logout: vi.fn() }),
}));

vi.mock("../../contexts/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", setTheme: vi.fn(), isDark: false }),
}));

const mockedWorkspaces = vi.mocked(clientModule.workspaces);

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

beforeEach(() => {
  vi.clearAllMocks();
  mockedWorkspaces.list.mockResolvedValue([]);
});

describe("Sidebar — conversation delete", () => {
  it("renders a delete button for each conversation", async () => {
    mockedWorkspaces.listConversations.mockResolvedValue(CONVERSATIONS);

    render(
      <Wrapper initialPath="/workspaces/my-ws/chat">
        <Sidebar />
      </Wrapper>
    );

    await waitFor(() =>
      expect(screen.getByText("First Chat")).toBeInTheDocument()
    );

    const deleteButtons = screen.getAllByRole("button", {
      name: /delete conversation/i,
    });
    expect(deleteButtons).toHaveLength(2);
  });

  it("calls deleteConversation with the correct id", async () => {
    mockedWorkspaces.listConversations.mockResolvedValue(CONVERSATIONS);
    mockedWorkspaces.deleteConversation.mockResolvedValue(undefined);

    render(
      <Wrapper initialPath="/workspaces/my-ws/chat">
        <Sidebar />
      </Wrapper>
    );

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

  it("does not render delete buttons when no conversations", async () => {
    mockedWorkspaces.listConversations.mockResolvedValue([]);

    render(
      <Wrapper initialPath="/workspaces/my-ws/chat">
        <Sidebar />
      </Wrapper>
    );

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /delete conversation/i })
      ).not.toBeInTheDocument();
    });
  });
});
