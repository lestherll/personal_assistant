import {
  createContext,
  useContext,
  useEffect,
  useReducer,
  type ReactNode,
} from "react";
import { auth, type UserResponse, UnauthorizedError } from "../api/client";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  user: UserResponse | null;
  status: AuthStatus;
}

type AuthAction =
  | { type: "SET_USER"; user: UserResponse }
  | { type: "CLEAR" }
  | { type: "LOADING" };

function reducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case "SET_USER":
      return { user: action.user, status: "authenticated" };
    case "CLEAR":
      return { user: null, status: "unauthenticated" };
    case "LOADING":
      return { ...state, status: "loading" };
  }
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const REFRESH_TOKEN_KEY = "refresh_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    user: null,
    status: "loading",
  });

  useEffect(() => {
    const refresh = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!refresh) {
      dispatch({ type: "CLEAR" });
      return;
    }

    auth
      .refresh(refresh)
      .then((tokens) => {
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
        // Cookie is set server-side; we fetch the current user from the token
        // by making an authenticated request. Use the workspace list as a
        // lightweight probe — if it succeeds we're authenticated.
        // We don't have a /auth/me endpoint so synthesise a minimal user.
        dispatch({
          type: "SET_USER",
          user: {
            id: "",
            username: "",
            email: "",
            created_at: new Date().toISOString(),
          },
        });
      })
      .catch((err) => {
        if (err instanceof UnauthorizedError) {
          localStorage.removeItem(REFRESH_TOKEN_KEY);
        }
        dispatch({ type: "CLEAR" });
      });
  }, []);

  async function login(username: string, password: string) {
    const tokens = await auth.login(username, password);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    dispatch({
      type: "SET_USER",
      user: { id: "", username, email: "", created_at: new Date().toISOString() },
    });
  }

  async function register(username: string, email: string, password: string) {
    const resp = await auth.register(username, email, password);
    localStorage.setItem(REFRESH_TOKEN_KEY, resp.tokens.refresh_token);
    dispatch({ type: "SET_USER", user: resp.user });
  }

  async function logout() {
    await auth.logout().catch(() => {});
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    dispatch({ type: "CLEAR" });
  }

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
