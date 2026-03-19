import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { workspaces } from "../api/client";
import { useCommandPalette } from "../hooks/useCommandPalette";

export function CommandPalette() {
  const { open, close } = useCommandPalette();
  const navigate = useNavigate();

  const { data: wspaces } = useQuery({
    queryKey: ["workspaces"],
    queryFn: workspaces.list,
  });

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh] bg-black/50"
      onClick={close}
    >
      <div
        className="w-full max-w-lg rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-900"
        onClick={(e) => e.stopPropagation()}
      >
        <Command className="text-sm">
          <Command.Input
            autoFocus
            placeholder="Search workspaces, commands…"
            className="w-full border-b border-gray-200 bg-transparent px-4 py-3 outline-none dark:border-gray-700 dark:text-gray-100"
          />
          <Command.List className="max-h-64 overflow-y-auto p-2">
            <Command.Empty className="py-4 text-center text-gray-400">
              No results found.
            </Command.Empty>

            {wspaces && wspaces.length > 0 && (
              <Command.Group heading="Workspaces" className="text-xs text-gray-400 px-2 py-1">
                {wspaces.map((ws) => (
                  <Command.Item
                    key={ws.name}
                    value={ws.name}
                    onSelect={() => {
                      navigate(`/workspaces/${ws.name}/chat`);
                      close();
                    }}
                    className="cursor-pointer rounded px-2 py-2 text-gray-800 hover:bg-gray-100 aria-selected:bg-violet-50 aria-selected:text-violet-700 dark:text-gray-200 dark:hover:bg-gray-800 dark:aria-selected:bg-violet-900/30"
                  >
                    {ws.name}
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            <Command.Group heading="Navigate" className="text-xs text-gray-400 px-2 py-1">
              <Command.Item
                value="usage dashboard"
                onSelect={() => { navigate("/usage"); close(); }}
                className="cursor-pointer rounded px-2 py-2 text-gray-800 hover:bg-gray-100 aria-selected:bg-violet-50 aria-selected:text-violet-700 dark:text-gray-200 dark:hover:bg-gray-800 dark:aria-selected:bg-violet-900/30"
              >
                Usage Dashboard
              </Command.Item>
              <Command.Item
                value="api keys"
                onSelect={() => { navigate("/settings/api-keys"); close(); }}
                className="cursor-pointer rounded px-2 py-2 text-gray-800 hover:bg-gray-100 aria-selected:bg-violet-50 aria-selected:text-violet-700 dark:text-gray-200 dark:hover:bg-gray-800 dark:aria-selected:bg-violet-900/30"
              >
                API Keys
              </Command.Item>
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
