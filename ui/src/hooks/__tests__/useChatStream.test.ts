import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useChatStream } from "../useChatStream";

function makeStreamResponse(events: string[], headers: Record<string, string> = {}) {
  const encoder = new TextEncoder();
  const chunks = events.map((e) => encoder.encode(`data: ${e}\n\n`));
  let index = 0;
  const stream = new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(chunks[index++]);
      } else {
        controller.close();
      }
    },
  });

  const responseHeaders = new Headers({
    "X-Conversation-Id": "conv-123",
    "X-Agent-Used": "assistant",
    ...headers,
  });

  return new Response(stream, { status: 200, headers: responseHeaders });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useChatStream", () => {
  it("streams tokens and appends to AI message", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      makeStreamResponse(["Hello", " world", "[DONE]"]),
    );

    const { result } = renderHook(() => useChatStream("test-ws", "assistant"));

    act(() => { result.current.send("Hi"); });

    await waitFor(() => expect(result.current.isStreaming).toBe(false));

    const msgs = result.current.messages;
    expect(msgs).toHaveLength(2);
    expect(msgs[0]).toEqual({ role: "human", content: "Hi" });
    expect(msgs[1]).toEqual({ role: "ai", content: "Hello world" });
  });

  it("sets isStreaming=false after [DONE]", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeStreamResponse(["[DONE]"]));
    const { result } = renderHook(() => useChatStream("ws", "agent"));
    act(() => { result.current.send("test"); });
    await waitFor(() => expect(result.current.isStreaming).toBe(false));
  });

  it("sets error on [ERROR] sentinel", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeStreamResponse(["[ERROR]"]));
    const { result } = renderHook(() => useChatStream("ws", "agent"));
    act(() => { result.current.send("test"); });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.isStreaming).toBe(false);
  });

  it("stop() aborts the stream", async () => {

    vi.mocked(fetch).mockImplementationOnce(
      (_url, init) => new Promise((_resolve, reject) => {
        (init as RequestInit).signal?.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      }),
    );

    const { result } = renderHook(() => useChatStream("ws", "agent"));
    act(() => { result.current.send("test"); });
    act(() => { result.current.stop(); });

    await waitFor(() => expect(result.current.isStreaming).toBe(false));
  });

  it("loadConversation restores message history", async () => {
    const messages = [
      { id: "1", conversation_id: "conv-1", role: "human", content: "Hello", agent_id: null, created_at: "" },
      { id: "2", conversation_id: "conv-1", role: "ai", content: "Hi there", agent_id: null, created_at: "" },
    ];
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(messages), { status: 200 }),
    );

    const { result } = renderHook(() => useChatStream("ws", "agent"));
    await act(async () => { await result.current.loadConversation("conv-1"); });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.conversationId).toBe("conv-1");
  });
});
