import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { AuthProvider, useAuth } from "../AuthContext";
import * as clientModule from "../../api/client";

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
      </AuthProvider>
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
      </AuthProvider>
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
      </AuthProvider>
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
      </AuthProvider>
    );

    await act(async () => {
      await loginFn("bob", "pass");
    });

    expect(screen.getByTestId("username").textContent).toBe("bob");
    expect(localStorage.getItem("refresh_token")).toBe("rt");
  });
});
