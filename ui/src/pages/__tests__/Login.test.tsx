import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Login } from "../Login";
import * as clientModule from "../../api/client";

const mockLogin = vi.fn();
const mockRegister = vi.fn();
vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({ login: mockLogin, register: mockRegister }),
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

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

describe("Login page", () => {
  it("renders login tab by default", () => {
    render(<Login />, { wrapper: Wrapper });
    // Submit button says "Login"; tab button also says "Login" — use the submit type
    expect(screen.getByRole("button", { name: /^login$/i, hidden: false })).toBeInTheDocument();
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
  });

  it("shows email field on register tab", () => {
    render(<Login />, { wrapper: Wrapper });
    // Click the tab button (first button with "Register" text)
    const registerTab = screen.getAllByRole("button", { name: /register/i })[0];
    fireEvent.click(registerTab);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it("calls login and navigates on success", async () => {
    mockLogin.mockResolvedValue(undefined);
    render(<Login />, { wrapper: Wrapper });

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: /^login$/i }));

    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith("alice", "secret"));
    expect(mockNavigate).toHaveBeenCalledWith("/workspaces", { replace: true });
  });

  it("shows error message on login failure", async () => {
    mockLogin.mockRejectedValue(new clientModule.ApiError(401, "Invalid credentials"));
    render(<Login />, { wrapper: Wrapper });

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /^login$/i }));

    await waitFor(() => expect(screen.getByText(/error 401/i)).toBeInTheDocument());
  });

  it("shows generic error message for non-ApiError failures", async () => {
    mockLogin.mockRejectedValue(new Error("Network error"));
    render(<Login />, { wrapper: Wrapper });

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "fail" } });
    fireEvent.click(screen.getByRole("button", { name: /^login$/i }));

    await waitFor(() =>
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    );
  });

  it("calls register and navigates on success", async () => {
    mockRegister.mockResolvedValue(undefined);
    render(<Login />, { wrapper: Wrapper });

    const registerTab = screen.getAllByRole("button", { name: /register/i })[0];
    fireEvent.click(registerTab);
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() =>
      expect(mockRegister).toHaveBeenCalledWith("alice", "a@example.com", "secret")
    );
    expect(mockNavigate).toHaveBeenCalledWith("/workspaces", { replace: true });
  });
});
