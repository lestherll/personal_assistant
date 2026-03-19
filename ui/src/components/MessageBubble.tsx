import { useCallback } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

interface Props {
  role: "human" | "ai";
  content: string;
  isStreaming?: boolean;
}

export function MessageBubble({ role, content, isStreaming }: Props) {
  const copyCode = useCallback((code: string) => {
    navigator.clipboard.writeText(code).catch(() => {});
  }, []);

  if (role === "human") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-violet-600 px-4 py-2 text-sm text-white">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-gray-100 px-4 py-2 text-sm dark:bg-gray-800 dark:text-gray-100">
        <ReactMarkdown
          rehypePlugins={[rehypeHighlight]}
          components={{
            pre({ children, ...props }) {
              type ReactChild = { props?: { children?: unknown } };
              const codeEl = (children as ReactChild)?.props;
              const code: string = typeof codeEl?.children === "string" ? codeEl.children : "";
              return (
                <div className="group relative">
                  <pre {...props}>{children}</pre>
                  <button
                    onClick={() => copyCode(code)}
                    className="absolute right-2 top-2 hidden rounded bg-gray-700 px-2 py-1 text-xs text-white group-hover:block"
                  >
                    Copy
                  </button>
                </div>
              );
            },
          }}
        >
          {content}
        </ReactMarkdown>
        {isStreaming && (
          <span className="inline-block w-0.5 h-4 bg-gray-500 animate-pulse ml-0.5 align-middle" />
        )}
      </div>
    </div>
  );
}
