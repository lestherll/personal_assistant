import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageBubble } from "../MessageBubble";

beforeEach(() => {
  Object.assign(navigator, {
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

describe("MessageBubble — human", () => {
  it("renders plain text without markdown", () => {
    render(<MessageBubble role="human" content="**hello**" />);
    expect(screen.getByText("**hello**")).toBeInTheDocument();
  });

  it("is right-aligned", () => {
    const { container } = render(<MessageBubble role="human" content="hi" />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("justify-end");
  });
});

describe("MessageBubble — ai", () => {
  it("renders markdown bold", () => {
    render(<MessageBubble role="ai" content="**bold text**" />);
    expect(screen.getByText("bold text").tagName).toBe("STRONG");
  });

  it("does NOT inject raw HTML from content", () => {
    const { container } = render(
      <MessageBubble role="ai" content="<script>alert(1)</script>" />,
    );
    expect(container.querySelector("script")).toBeNull();
  });

  it("shows streaming cursor when isStreaming=true", () => {
    const { container } = render(
      <MessageBubble role="ai" content="typing…" isStreaming />,
    );
    // The cursor span has animate-pulse class
    const cursor = container.querySelector(".animate-pulse");
    expect(cursor).toBeInTheDocument();
  });

  it("does not show streaming cursor when isStreaming=false", () => {
    const { container } = render(<MessageBubble role="ai" content="done" />);
    expect(container.querySelector(".animate-pulse")).toBeNull();
  });
});
