import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { workspaces, agents, ApiError } from "../api/client";

export function WorkspaceList() {
  const qc = useQueryClient();
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["workspaces"],
    queryFn: workspaces.list,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const ws = await workspaces.create(newName, newDesc);
      // Agent creation is best-effort — workspace is usable without it
      try {
        await agents.create(ws.name, {
          name: "assistant",
          description:
            "A general-purpose assistant that handles a wide range of tasks: " +
            "answering questions, summarising content, drafting text, and more.",
          system_prompt:
            "You are a helpful personal assistant. " +
            "Help the user with questions, analysis, writing, and any task they bring you. " +
            "Be concise, accurate, and proactive about asking for clarification when needed.",
        });
      } catch {
        return { agentFailed: true };
      }
      return { agentFailed: false };
    },
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["workspaces"] });
      setNewName("");
      setNewDesc("");
      if (result?.agentFailed) {
        setError("Workspace created — default agent setup failed. You can add one from the chat page.");
      } else {
        setError(null);
      }
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Failed to create workspace");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => workspaces.delete(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspaces"] }),
  });

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h2 className="mb-6 text-xl font-semibold text-gray-900 dark:text-white">Workspaces</h2>

      {isLoading ? (
        <p className="text-gray-500">Loading…</p>
      ) : (
        <ul className="mb-8 space-y-2">
          {data?.map((ws) => (
            <li
              key={ws.name}
              className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900"
            >
              <div>
                <Link
                  to={`/workspaces/${ws.name}/chat`}
                  className="font-medium text-violet-600 hover:underline dark:text-violet-400"
                >
                  {ws.name}
                </Link>
                {ws.description && (
                  <p className="mt-0.5 text-xs text-gray-500">{ws.description}</p>
                )}
              </div>
              <div className="flex gap-2">
                <Link
                  to={`/workspaces/${ws.name}/conversations`}
                  className="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
                >
                  History
                </Link>
                <button
                  onClick={() => {
                    if (confirm(`Delete workspace "${ws.name}"?`)) {
                      deleteMutation.mutate(ws.name);
                    }
                  }}
                  className="rounded px-2 py-1 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
          {data?.length === 0 && (
            <li className="text-sm text-gray-500">No workspaces yet. Create one below.</li>
          )}
        </ul>
      )}

      {/* Create form */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <h3 className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
          New workspace
        </h3>
        <div className="flex flex-col gap-2">
          <input
            type="text"
            placeholder="Name (letters, numbers, hyphens)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-violet-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-violet-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
          {error && <p className="text-xs text-red-500">{error}</p>}
          <button
            onClick={() => createMutation.mutate()}
            disabled={!newName.trim() || createMutation.isPending}
            className="rounded-lg bg-violet-600 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {createMutation.isPending ? "Creating…" : "Create workspace"}
          </button>
        </div>
      </div>
    </div>
  );
}
