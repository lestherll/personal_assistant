import { useCallback, useRef, useState } from "react";
import { streamChat, workspaces, type MessageResponse, type TitleMode } from "../api/client";

interface LocalMessage {
  role: "human" | "ai";
  content: string;
}

interface ChatStreamState {
  messages: LocalMessage[];
  isStreaming: boolean;
  conversationId: string | null;
  error: string | null;
}

export function useChatStream(workspaceName: string, agentName: string, titleMode: TitleMode = "first_20_words") {
  const [state, setState] = useState<ChatStreamState>({
    messages: [],
    isStreaming: false,
    conversationId: null,
    error: null,
  });

  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (message: string) => {
      const controller = new AbortController();
      abortRef.current = controller;

      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          { role: "human", content: message },
          { role: "ai", content: "" },
        ],
        isStreaming: true,
        error: null,
      }));

      try {
        const { conversationId } = await streamChat(
          `/workspaces/${workspaceName}/chat/stream`,
          {
            message,
            ...(agentName && agentName !== "auto" ? { agent_name: agentName } : {}),
            conversation_id: state.conversationId ?? undefined,
            // Only send title_mode on the first turn; subsequent turns are no-ops anyway
            ...(state.conversationId == null ? { title_mode: titleMode } : {}),
          },
          (token) => {
            setState((prev) => {
              const msgs = [...prev.messages];
              const last = msgs[msgs.length - 1];
              msgs[msgs.length - 1] = { ...last, content: last.content + token };
              return { ...prev, messages: msgs };
            });
          },
          controller.signal,
        );

        setState((prev) => ({
          ...prev,
          isStreaming: false,
          conversationId: prev.conversationId ?? conversationId,
        }));
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          setState((prev) => ({ ...prev, isStreaming: false }));
          return;
        }
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          error: err instanceof Error ? err.message : "Unknown error",
        }));
      }
    },
    [workspaceName, agentName, titleMode, state.conversationId],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const loadConversation = useCallback(
    async (conversationId: string) => {
      const msgs = await workspaces.getMessages(workspaceName, conversationId);
      setState({
        messages: msgs
          .filter((m): m is MessageResponse & { role: "human" | "ai" } =>
            m.role === "human" || m.role === "ai",
          )
          .map((m) => ({ role: m.role, content: m.content })),
        isStreaming: false,
        conversationId,
        error: null,
      });
    },
    [workspaceName],
  );

  const clear = useCallback(() => {
    setState({ messages: [], isStreaming: false, conversationId: null, error: null });
  }, []);

  return { ...state, send, stop, loadConversation, clear };
}
