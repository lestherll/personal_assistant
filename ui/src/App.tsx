import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Route, Routes, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthProvider, getSmartRedirectPath } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Layout } from "./components/Layout";
import { CommandPalette } from "./components/CommandPalette";

import { Login } from "./pages/Login";
import { WorkspaceList } from "./pages/WorkspaceList";
import { Chat } from "./pages/Chat";
import { AgentConfig } from "./pages/AgentConfig";
import { ConversationHistory } from "./pages/ConversationHistory";
import { ApiKeys } from "./pages/ApiKeys";

const UsageDashboard = lazy(() =>
  import("./pages/UsageDashboard").then((m) => ({ default: m.UsageDashboard })),
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
});

function Spinner() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-violet-500 border-t-transparent" />
    </div>
  );
}

function SmartRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    getSmartRedirectPath().then((path) => navigate(path, { replace: true }));
  }, [navigate]);
  return <Spinner />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          <BrowserRouter>
            <CommandPalette />
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route index element={<SmartRedirect />} />
                  <Route path="/workspaces" element={<WorkspaceList />} />
                  <Route path="/workspaces/:name/chat" element={<Chat />} />
                  <Route path="/workspaces/:name/chat/:convId" element={<Chat />} />
                  <Route path="/workspaces/:name/agents/new" element={<AgentConfig />} />
                  <Route path="/workspaces/:name/agents/:agent" element={<AgentConfig />} />
                  <Route path="/workspaces/:name/conversations" element={<ConversationHistory />} />
                  <Route
                    path="/usage"
                    element={
                      <Suspense fallback={<Spinner />}>
                        <UsageDashboard />
                      </Suspense>
                    }
                  />
                  <Route path="/settings/api-keys" element={<ApiKeys />} />
                </Route>
              </Route>
            </Routes>
          </BrowserRouter>
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
