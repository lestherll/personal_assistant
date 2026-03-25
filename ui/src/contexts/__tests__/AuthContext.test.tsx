import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "../AuthContext";
import * as clientModule from "../../api/client";
import type { ReactNode } from "react";

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof clientModule>("../../api/client");
  return {
    ...actual,
    auth: {
      ...actual.auth,
      refresh: vi.fn(),
      me: vi.fn(),
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    },
    setUnauthorizedHandler: vi.fn(),
  };
});

const mockedAuth = vi.mocked(clientModule.auth);

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function makeWrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function StatusDisplay() {
  const { status, user } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="username">{user?.username ?? "none"}</span>
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("AuthContext", () => {
  it("starts as 'unauthenticated' when no refresh token is stored", async () => {
    render(
      <AuthProvider>
        <StatusDisplay />
      </AuthProvider>,
      { wrapper: makeWrapper(makeQueryClient()) }
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated")
    );
  });

  it("restores session from stored refresh token and populates real username via /auth/me", async () => {
    localStorage.setItem("refresh_token", "stored-refresh");
    mockedAuth.refresh.mockResolvedValue({
      access_token: "new-access",
      refresh_token: "new-refresh",
    });
    mockedAuth.me.mockResolvedValue({
      id: "user-1",
      username: "alice",
      email: "alice@example.com",
      created_at: new Date().toISOString(),
    });

    render(
      <AuthProvider>
        <StatusDisplay />
      </AuthProvider>,
      { wrapper: makeWrapper(makeQueryClient()) }
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("authenticated")
    );
    expect(screen.getByTestId("username").textContent).toBe("alice");
    expect(localStorage.getItem("refresh_token")).toBe("new-refresh");
  });

  it("clears state when stored refresh token is invalid", async () => {
    localStorage.setItem("refresh_token", "bad-token");
    mockedAuth.refresh.mockRejectedValue(new clientModule.UnauthorizedError());

    render(
      <AuthProvider>
        <StatusDisplay />
      </AuthProvider>,
      { wrapper: makeWrapper(makeQueryClient()) }
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated")
    );
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("login: stores refresh token and fetches real profile via /auth/me", async () => {
    mockedAuth.login.mockResolvedValue({
      access_token: "at",
      refresh_token: "rt",
    });
    mockedAuth.me.mockResolvedValue({
      id: "user-2",
      username: "bob",
      email: "bob@example.com",
      created_at: new Date().toISOString(),
    });

    let loginFn!: (u: string, p: string) => Promise<void>;
    function Capturer() {
      const { login } = useAuth();
      loginFn = login;
      return null;
    }

    render(
      <AuthProvider>
        <Capturer />
        <StatusDisplay />
      </AuthProvider>,
      { wrapper: makeWrapper(makeQueryClient()) }
    );

    await act(async () => {
      await loginFn("bob", "pass");
    });

    expect(screen.getByTestId("username").textContent).toBe("bob");
    expect(localStorage.getItem("refresh_token")).toBe("rt");
  });

  it("logout: clears the query cache", async () => {
    mockedAuth.logout.mockResolvedValue(undefined);
    const qc = makeQueryClient();
    const clearSpy = vi.spyOn(qc, "clear");

    let logoutFn!: () => Promise<void>;
    function Capturer() {
      const { logout } = useAuth();
      logoutFn = logout;
      return null;
    }

    render(
      <AuthProvider>
        <Capturer />
        <StatusDisplay />
      </AuthProvider>,
      { wrapper: makeWrapper(qc) }
    );

    await act(async () => { await logoutFn(); });

    expect(clearSpy).toHaveBeenCalledOnce();
    expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
  });

  it("session expiry (401 handler): clears the query cache", async () => {
    // No refresh token at mount so the session-restore effect does not consume
    // it — it just dispatches CLEAR immediately without touching localStorage.
    const qc = makeQueryClient();
    const clearSpy = vi.spyOn(qc, "clear");

    let capturedHandler!: () => Promise<boolean>;
    vi.mocked(clientModule.setUnauthorizedHandler).mockImplementation((h) => {
      capturedHandler = h;
    });

    render(
      <AuthProvider>
        <StatusDisplay />
      </AuthProvider>,
      { wrapper: makeWrapper(qc) }
    );

    await waitFor(() => expect(capturedHandler).toBeDefined());

    // Simulate a 401 event: provide a token and make refresh fail
    localStorage.setItem("refresh_token", "expired-token");
    mockedAuth.refresh.mockRejectedValue(new clientModule.UnauthorizedError());

    await act(async () => { await capturedHandler(); });

    expect(clearSpy).toHaveBeenCalledOnce();
    expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
  });
});
