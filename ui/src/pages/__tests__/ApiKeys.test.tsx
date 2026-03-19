import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiKeys } from "../ApiKeys";
import * as clientModule from "../../api/client";

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof clientModule>("../../api/client");
  return {
    ...actual,
    auth: {
      ...actual.auth,
      listApiKeys: vi.fn(),
      createApiKey: vi.fn(),
      revokeApiKey: vi.fn(),
    },
  };
});

const mockedAuth = vi.mocked(clientModule.auth);

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => vi.clearAllMocks());

describe("ApiKeys page", () => {
  it("shows empty state when no keys exist", async () => {
    mockedAuth.listApiKeys.mockResolvedValue([]);
    render(<ApiKeys />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByText(/no api keys yet/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/programmatically/i)).toBeInTheDocument();
  });

  it("disables create button when name is empty", async () => {
    mockedAuth.listApiKeys.mockResolvedValue([]);
    render(<ApiKeys />, { wrapper: Wrapper });

    await waitFor(() => screen.getByRole("button", { name: /create/i }));
    expect(screen.getByRole("button", { name: /^create$/i })).toBeDisabled();
  });

  it("shows revealed key after successful creation", async () => {
    mockedAuth.listApiKeys.mockResolvedValue([]);
    mockedAuth.createApiKey.mockResolvedValue({
      id: "1",
      name: "test-key",
      key: "sk-abc123xyz",
      key_prefix: "sk-abc",
      is_active: true,
      created_at: new Date().toISOString(),
      expires_at: null,
      last_used_at: null,
    });
    render(<ApiKeys />, { wrapper: Wrapper });

    await waitFor(() => screen.getByPlaceholderText(/key name/i));
    fireEvent.change(screen.getByPlaceholderText(/key name/i), {
      target: { value: "test-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() =>
      expect(screen.getByText(/shown once/i)).toBeInTheDocument()
    );
    expect(screen.getByText("sk-abc123xyz")).toBeInTheDocument();
  });

  it("renders active key with revoke button", async () => {
    mockedAuth.listApiKeys.mockResolvedValue([
      {
        id: "1",
        name: "my-key",
        key_prefix: "sk-abc",
        is_active: true,
        created_at: new Date().toISOString(),
        expires_at: null,
        last_used_at: null,
      },
    ]);
    render(<ApiKeys />, { wrapper: Wrapper });

    await waitFor(() => expect(screen.getByText("my-key")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /revoke/i })).toBeInTheDocument();
  });
});
