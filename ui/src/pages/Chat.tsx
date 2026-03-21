import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { workspaces, type TitleMode } from "../api/client";
import { useChatStream } from "../hooks/useChatStream";
import { MessageBubble } from "../components/MessageBubble";
import { ChatInput } from "../components/ChatInput";

export function Chat() {
  const { name = "", convId } = useParams<{ name: string; convId?: string }>();
  const navigate = useNavigate();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [titleMode, setTitleMode] = useState<TitleMode>(
    () => (localStorage.getItem("titleMode") as TitleMode | null) ?? "first_20_words",
  );

  const { data: workspace } = useQuery({
    queryKey: ["workspace", name],
    queryFn: () => workspaces.get(name),
    enabled: !!name,
  });

  const { messages, isStreaming, conversationId, error, send, stop, loadConversation, clear } =
    useChatStream(name, selectedAgent, titleMode);

  // Reset selected agent and messages when workspace changes
  useEffect(() => {
    setSelectedAgent("auto");
    clear();
  }, [name]); // eslint-disable-line react-hooks/exhaustive-deps

  // Default to "auto" once workspace loads if nothing is selected yet
  useEffect(() => {
    if (workspace && !selectedAgent) {
      setSelectedAgent("auto");
    }
  }, [workspace, selectedAgent]);

  // Load conversation from URL param
  useEffect(() => {
    if (convId && convId !== conversationId) {
      clear();
      loadConversation(convId);
    }
  }, [convId, conversationId, loadConversation, clear]);

  // Update URL after first reply
  useEffect(() => {
    if (conversationId && !convId) {
      navigate(`/workspaces/${name}/chat/${conversationId}`, { replace: true });
    }
  }, [conversationId, convId, name, navigate]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Reset on agent change
  function handleAgentChange(agent: string) {
    setSelectedAgent(agent);
    clear();
    navigate(`/workspaces/${name}/chat`, { replace: true });
  }

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b border-gray-200 px-4 py-2 dark:border-gray-700">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{name}</span>
        {workspace?.agents && workspace.agents.length > 0 && (
          <select
            value={selectedAgent}
            onChange={(e) => handleAgentChange(e.target.value)}
            className="rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
          >
            <option value="auto">Auto</option>
            {workspace.agents.map((a) => (
              <option key={a.config.name} value={a.config.name}>
                {a.config.name}
              </option>
            ))}
          </select>
        )}
        <select
          value={titleMode}
          onChange={(e) => {
            const mode = e.target.value as TitleMode;
            setTitleMode(mode);
            localStorage.setItem("titleMode", mode);
          }}
          className="ml-auto rounded border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
          title="How new conversation titles are generated"
        >
          <option value="first_20_words">Title: first words</option>
          <option value="llm">Title: AI</option>
          <option value="untitled">Title: none</option>
        </select>
        <button
          onClick={() => { clear(); navigate(`/workspaces/${name}/chat`, { replace: true }); }}
          className="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          New chat
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {workspace && workspace.agents.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              This workspace has no agents yet.
            </p>
            <button
              onClick={() => navigate(`/workspaces/${name}/agents/new`)}
              className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700"
            >
              Create an agent
            </button>
          </div>
        ) : (
          <>
            {messages.length === 0 && !isStreaming && (
              <div className="flex h-full items-center justify-center text-sm text-gray-400">
                Start a conversation with {selectedAgent || "your assistant"}
              </div>
            )}
            {messages.map((msg, i) => (
              <MessageBubble
                key={i}
                role={msg.role}
                content={msg.content}
                isStreaming={isStreaming && i === messages.length - 1 && msg.role === "ai"}
              />
            ))}
            {error && (
              <p className="text-center text-xs text-red-500">{error}</p>
            )}
            <div ref={bottomRef} />
          </>
        )}
      </div>

      {/* Input — disabled only while workspace is loading or has no agents */}
      <ChatInput
        onSend={send}
        onStop={stop}
        isStreaming={isStreaming}
        disabled={!workspace || workspace.agents.length === 0}
      />
    </div>
  );
}
