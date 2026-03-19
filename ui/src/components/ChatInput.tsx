import { type KeyboardEvent, useRef, useState } from "react";

interface Props {
  onSend: (message: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export function ChatInput({ onSend, onStop, isStreaming, disabled }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const msg = value.trim();
    if (!msg || isStreaming) return;
    setValue("");
    onSend(msg);
  }

  return (
    <div className="flex gap-2 border-t border-gray-200 p-3 dark:border-gray-700">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Message… (Enter to send, Shift+Enter for newline)"
        rows={1}
        disabled={disabled || isStreaming}
        className="flex-1 resize-none rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:border-violet-500 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 disabled:opacity-50"
        style={{ maxHeight: 200, overflowY: "auto" }}
      />
      {isStreaming ? (
        <button
          onClick={onStop}
          className="rounded-lg bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600"
        >
          Stop
        </button>
      ) : (
        <button
          onClick={submit}
          disabled={!value.trim() || disabled}
          className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-40"
        >
          Send
        </button>
      )}
    </div>
  );
}
