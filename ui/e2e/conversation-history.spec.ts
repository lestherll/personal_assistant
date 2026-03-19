import { test, expect } from "./fixtures";

const CONVERSATIONS = [
  {
    id: "conv-1",
    title: "First conversation",
    created_at: "2024-01-01T10:00:00Z",
    updated_at: "2024-01-01T11:00:00Z",
  },
  {
    id: "conv-2",
    title: "Second conversation",
    created_at: "2024-01-02T10:00:00Z",
    updated_at: "2024-01-02T11:00:00Z",
  },
];

const MESSAGES = [
  {
    id: "msg-1",
    conversation_id: "conv-1",
    role: "human",
    content: "Hello there",
    agent_id: null,
    created_at: "2024-01-01T10:00:00Z",
  },
  {
    id: "msg-2",
    conversation_id: "conv-1",
    role: "ai",
    content: "Hi! How can I help?",
    agent_id: null,
    created_at: "2024-01-01T10:00:01Z",
  },
];

test.describe("ConversationHistory page", () => {
  test("shows empty state when workspace has no conversations", async ({
    authedPage: page,
  }) => {
    // fixture's fallback already returns [] for conversations; no override needed
    await page.goto("/workspaces/my-ws/conversations");

    await expect(page.getByText(/no conversations here yet/i)).toBeVisible();
    await expect(
      page.getByRole("link", { name: /go to chat/i })
    ).toBeVisible();
  });

  test("shows list of conversations in the left panel", async ({
    authedPage: page,
  }) => {
    // Override fixture fallback: return real conversations for this workspace
    await page.route("**/api/workspaces/my-ws/conversations*", (route) =>
      route.fulfill({ json: CONVERSATIONS })
    );
    await page.goto("/workspaces/my-ws/conversations");

    // Conversation list items are <button> elements in the left panel
    await expect(page.getByRole("button", { name: /First conversation/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Second conversation/i })).toBeVisible();
  });

  test("selecting a conversation loads messages in the right panel", async ({
    authedPage: page,
  }) => {
    // Use ** to match both the list URL and the /messages sub-path
    await page.route("**/api/workspaces/my-ws/conversations**", async (route) => {
      const url = route.request().url();
      if (url.includes("/messages")) {
        await route.fulfill({ json: MESSAGES });
      } else {
        await route.fulfill({ json: CONVERSATIONS });
      }
    });

    await page.goto("/workspaces/my-ws/conversations");

    // Right panel shows "select a conversation" prompt initially
    await expect(
      page.getByText(/select a conversation on the left/i)
    ).toBeVisible();

    // Click first conversation button in left panel
    await page.getByRole("button", { name: /First conversation/i }).click();

    // Messages appear in the right panel
    await expect(page.getByText("Hello there")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("Hi! How can I help?")).toBeVisible();
  });

  test("search input is visible and filters conversations", async ({
    authedPage: page,
  }) => {
    await page.route("**/api/workspaces/my-ws/conversations*", async (route) => {
      const url = route.request().url();
      if (url.includes("q=First")) {
        await route.fulfill({ json: [CONVERSATIONS[0]] });
      } else {
        await route.fulfill({ json: CONVERSATIONS });
      }
    });

    await page.goto("/workspaces/my-ws/conversations");
    await expect(page.getByRole("button", { name: /First conversation/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Second conversation/i })).toBeVisible();

    // Type in search box — debounce is 300ms, wait for re-query
    await page.fill('input[placeholder*="Search"]', "First");
    await expect(page.getByRole("button", { name: /Second conversation/i })).not.toBeVisible({
      timeout: 2000,
    });
    await expect(page.getByRole("button", { name: /First conversation/i })).toBeVisible();
  });

  test("'Go to chat' link in empty state points to workspace chat", async ({
    authedPage: page,
  }) => {
    // fixture fallback returns [] — workspace has no conversations
    await page.goto("/workspaces/my-ws/conversations");

    const link = page.getByRole("link", { name: /go to chat/i });
    await expect(link).toHaveAttribute("href", "/workspaces/my-ws/chat");
  });
});
