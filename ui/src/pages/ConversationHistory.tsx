import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { workspaces, type MessageResponse } from "../api/client";
import { MessageBubble } from "../components/MessageBubble";

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export function ConversationHistory() {
  const { name = "" } = useParams<{ name: string }>();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const queryClient = useQueryClient();

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["conversations", name, debouncedSearch],
    queryFn: () => workspaces.listConversations(name, { q: debouncedSearch || undefined }),
  });

  const { data: messages } = useQuery<MessageResponse[]>({
    queryKey: ["messages", name, selectedId],
    queryFn: () => workspaces.getMessages(name, selectedId!),
    enabled: !!selectedId,
  });

  const deleteMutation = useMutation({
    mutationFn: (conversationId: string) =>
      workspaces.deleteConversation(name, conversationId),
    onSuccess: (_data, conversationId) => {
      queryClient.invalidateQueries({ queryKey: ["conversations", name] });
      if (selectedId === conversationId) {
        setSelectedId(null);
      }
    },
  });

  const listRef = useRef<HTMLDivElement>(null);

  return (
    <div className="flex h-full">
      {/* Conversation list */}
      <div className="flex w-72 flex-shrink-0 flex-col border-r border-gray-200 dark:border-gray-700">
        <div className="p-3">
          <input
            type="text"
            placeholder="Search conversations…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-violet-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </div>
        <div ref={listRef} className="flex-1 overflow-y-auto">
          {isLoading && <p className="px-3 text-xs text-gray-400">Loading…</p>}
          {conversations?.map((conv) => (
            <div
              key={conv.id}
              className={`group relative border-b border-gray-100 dark:border-gray-800 ${
                selectedId === conv.id ? "bg-violet-50 dark:bg-violet-900/20" : ""
              }`}
            >
              <button
                onClick={() => setSelectedId(conv.id)}
                className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                <p className="truncate pr-6 font-medium text-gray-800 dark:text-gray-200">
                  {conv.title ?? "Untitled"}
                </p>
                <p className="mt-0.5 text-xs text-gray-400">
                  {new Date(conv.updated_at).toLocaleDateString()}
                </p>
              </button>
              <button
                aria-label="Delete conversation"
                onClick={() => deleteMutation.mutate(conv.id)}
                className="absolute right-2 top-2 hidden rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 group-hover:block dark:hover:bg-red-900/20"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                  <path fillRule="evenodd" d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.285a1.5 1.5 0 0 0 1.493-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5a.75.75 0 0 1 .786-.711Z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          ))}
          {conversations?.length === 0 && (
            <div className="px-3 py-6 text-center">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400">No conversations here yet</p>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Conversations appear after your first chat in this workspace.
              </p>
              <Link
                to={`/workspaces/${name}/chat`}
                className="mt-2 inline-block text-xs font-medium text-violet-600 hover:underline dark:text-violet-400"
              >
                Go to chat →
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Message preview */}
      <div className="flex flex-1 flex-col overflow-y-auto p-4 space-y-3">
        {!selectedId && (
          <div className="flex h-full items-center justify-center text-sm text-gray-400">
            ← Select a conversation on the left to read it here
          </div>
        )}
        {messages?.map((msg) =>
          msg.role === "human" || msg.role === "ai" ? (
            <MessageBubble key={msg.id} role={msg.role} content={msg.content} />
          ) : null,
        )}
      </div>
    </div>
  );
}
