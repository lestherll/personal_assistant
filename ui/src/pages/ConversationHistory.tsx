import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
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

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["conversations", name, debouncedSearch],
    queryFn: () => workspaces.listConversations(name, { q: debouncedSearch || undefined }),
  });

  const { data: messages } = useQuery<MessageResponse[]>({
    queryKey: ["messages", name, selectedId],
    queryFn: () => workspaces.getMessages(name, selectedId!),
    enabled: !!selectedId,
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
            <button
              key={conv.id}
              onClick={() => setSelectedId(conv.id)}
              className={`w-full border-b border-gray-100 px-3 py-2 text-left text-sm hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800 ${
                selectedId === conv.id ? "bg-violet-50 dark:bg-violet-900/20" : ""
              }`}
            >
              <p className="truncate font-medium text-gray-800 dark:text-gray-200">
                {conv.title ?? "Untitled"}
              </p>
              <p className="mt-0.5 text-xs text-gray-400">
                {new Date(conv.updated_at).toLocaleDateString()}
              </p>
            </button>
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
