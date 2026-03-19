import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WorkspaceList } from "../WorkspaceList";
import * as clientModule from "../../api/client";

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof clientModule>("../../api/client");
  return {
    ...actual,
    workspaces: {
      list: vi.fn(),
      create: vi.fn(),
      delete: vi.fn(),
    },
    agents: {
      create: vi.fn(),
    },
  };
});

const mockedWorkspaces = vi.mocked(clientModule.workspaces);
const mockedAgents = vi.mocked(clientModule.agents);

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("WorkspaceList", () => {
  it("renders empty state when there are no workspaces", async () => {
    mockedWorkspaces.list.mockResolvedValue([]);
    render(<WorkspaceList />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByText(/no workspaces yet/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/create your first workspace/i)).toBeInTheDocument();
  });

  it("renders workspace names when list is populated", async () => {
    mockedWorkspaces.list.mockResolvedValue([
      { name: "my-ws", description: "desc", agents: [], created_at: "", updated_at: "" },
    ]);
    render(<WorkspaceList />, { wrapper: Wrapper });

    await waitFor(() => expect(screen.getByText("my-ws")).toBeInTheDocument());
  });

  it("create button is disabled when name is empty", async () => {
    mockedWorkspaces.list.mockResolvedValue([]);
    render(<WorkspaceList />, { wrapper: Wrapper });

    await waitFor(() => screen.getByText(/create workspace/i));
    expect(screen.getByRole("button", { name: /create workspace/i })).toBeDisabled();
  });

  it("calls create and invalidates on success", async () => {
    mockedWorkspaces.list.mockResolvedValue([]);
    mockedWorkspaces.create.mockResolvedValue({
      name: "new-ws",
      description: "",
      agents: [],
      created_at: "",
      updated_at: "",
    });
    mockedAgents.create.mockResolvedValue({ config: { name: "assistant" } } as never);
    render(<WorkspaceList />, { wrapper: Wrapper });

    await waitFor(() => screen.getByRole("button", { name: /create workspace/i }));
    fireEvent.change(screen.getByPlaceholderText(/name/i), {
      target: { value: "new-ws" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create workspace/i }));

    await waitFor(() =>
      expect(mockedWorkspaces.create).toHaveBeenCalledWith("new-ws", "")
    );
  });
});
