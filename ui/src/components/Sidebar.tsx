import { Link, NavLink, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { workspaces } from "../api/client";
import { useTheme } from "../contexts/ThemeContext";
import { useAuth } from "../contexts/AuthContext";
import { Avatar } from "./Avatar";

type ThemeOption = "light" | "system" | "dark";
const THEME_OPTIONS: { value: ThemeOption; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "system", label: "Auto" },
  { value: "dark", label: "Dark" },
];

export function Sidebar() {
  const { name, convId } = useParams<{ name?: string; convId?: string }>();
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: wspaces } = useQuery({
    queryKey: ["workspaces"],
    queryFn: workspaces.list,
  });

  const { data: conversations } = useQuery({
    queryKey: ["conversations", name],
    queryFn: () => workspaces.listConversations(name!, { limit: 20 }),
    enabled: !!name,
  });

  const deleteMutation = useMutation({
    mutationFn: (conversationId: string) =>
      workspaces.deleteConversation(name!, conversationId),
    onSuccess: (_data, conversationId) => {
      queryClient.invalidateQueries({ queryKey: ["conversations", name] });
      if (convId === conversationId) {
        navigate(`/workspaces/${name}/chat`);
      }
    },
  });

  const displayName = user?.username || "you";

  return (
    <aside className="flex h-full w-64 flex-shrink-0 flex-col border-r border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900">
      {/* Header — user avatar + username */}
      <div className="flex items-center gap-3 border-b border-gray-200 p-4 dark:border-gray-700">
        <Avatar name={displayName} size="md" />
        <span className="truncate text-sm font-semibold text-gray-800 dark:text-gray-100">
          {displayName}
        </span>
      </div>

      {/* Workspace switcher */}
      <div className="p-3">
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Workspaces
        </p>
        {wspaces?.map((ws) => (
          <NavLink
            key={ws.name}
            to={`/workspaces/${ws.name}/chat`}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded px-2 py-1.5 text-sm ${
                isActive
                  ? "bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-200"
                  : "text-gray-700 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-gray-800"
              }`
            }
          >
            <Avatar name={ws.name} size="sm" />
            <span className="truncate">{ws.name}</span>
          </NavLink>
        ))}
        <Link
          to="/workspaces"
          className="mt-1 block rounded px-2 py-1.5 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        >
          + Manage workspaces
        </Link>
      </div>

      {/* Recent conversations */}
      {name && conversations && conversations.length > 0 && (
        <div className="flex-1 overflow-y-auto p-3">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Recent
          </p>
          {conversations.map((conv) => (
            <div key={conv.id} className="group relative flex items-center">
              <NavLink
                to={`/workspaces/${name}/chat/${conv.id}`}
                className={({ isActive }) =>
                  `block flex-1 truncate rounded px-2 py-1.5 text-xs ${
                    isActive
                      ? "bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-200"
                      : "text-gray-600 hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-800"
                  }`
                }
              >
                {conv.title ?? "Untitled conversation"}
              </NavLink>
              <button
                aria-label="Delete conversation"
                onClick={() => deleteMutation.mutate(conv.id)}
                className="absolute right-1 hidden rounded p-0.5 text-gray-400 hover:bg-red-50 hover:text-red-500 group-hover:flex dark:hover:bg-red-900/20"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
                  <path fillRule="evenodd" d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.285a1.5 1.5 0 0 0 1.493-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5a.75.75 0 0 1 .786-.711Z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="mt-auto flex flex-col gap-1 border-t border-gray-200 p-3 dark:border-gray-700">
        <NavLink
          to="/usage"
          className="rounded px-2 py-1.5 text-sm text-gray-600 hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          Usage
        </NavLink>
        <NavLink
          to="/settings/api-keys"
          className="rounded px-2 py-1.5 text-sm text-gray-600 hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          API Keys
        </NavLink>

        {/* 3-way theme selector */}
        <div className="mt-1 flex rounded-lg bg-gray-200 p-0.5 dark:bg-gray-800">
          {THEME_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTheme(opt.value)}
              className={`flex-1 rounded-md py-1 text-xs font-medium transition-colors ${
                theme === opt.value
                  ? "bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white"
                  : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              }`}
              aria-pressed={theme === opt.value}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <button
          onClick={logout}
          className="mt-1 rounded px-2 py-1.5 text-left text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
        >
          Logout
        </button>
      </div>
    </aside>
  );
}
