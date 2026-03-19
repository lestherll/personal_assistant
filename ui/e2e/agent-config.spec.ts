import { test, expect } from "./fixtures";

const PROVIDERS = [{ name: "anthropic" }, { name: "ollama" }];
const MODELS = ["claude-opus-4-5", "claude-sonnet-4-5"];

const EXISTING_AGENT = {
  config: {
    name: "my-agent",
    description: "A test agent",
    system_prompt: "You are a helpful assistant.",
    provider: null,
    model: null,
    allowed_tools: null,
  },
};

test.describe("AgentConfig — new agent", () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.route("**/api/providers/", (route) =>
      route.fulfill({ json: PROVIDERS })
    );
    await page.goto("/workspaces/my-ws/agents/new");
  });

  test("shows all required fields", async ({ authedPage: page }) => {
    await expect(page.getByText(/new agent/i)).toBeVisible();
    await expect(page.locator('input[type="text"]').first()).toBeVisible(); // Name
    await expect(page.locator("textarea")).toBeVisible(); // System prompt
    await expect(page.getByRole("combobox").first()).toBeVisible(); // Provider
  });

  test("save button is disabled until name and system prompt are filled", async ({
    authedPage: page,
  }) => {
    const saveBtn = page.getByRole("button", { name: /save agent/i });
    await expect(saveBtn).toBeDisabled();

    await page.locator('input[type="text"]').first().fill("my-agent");
    await expect(saveBtn).toBeDisabled(); // still missing system prompt

    await page.locator("textarea").fill("You are helpful.");
    await expect(saveBtn).toBeEnabled();
  });

  test("selecting a provider enables the model dropdown and loads models", async ({
    authedPage: page,
  }) => {
    await page.route("**/api/providers/anthropic/models", (route) =>
      route.fulfill({ json: { name: "anthropic", models: MODELS } })
    );

    const providerSelect = page.getByRole("combobox").first();
    const modelSelect = page.getByRole("combobox").nth(1);

    await expect(modelSelect).toBeDisabled();
    await providerSelect.selectOption("anthropic");
    await expect(modelSelect).toBeEnabled();
    // Select the first model to verify the options loaded
    await modelSelect.selectOption(MODELS[0]);
    await expect(modelSelect).toHaveValue(MODELS[0]);
  });

  test("cancel navigates back", async ({ authedPage: page }) => {
    await page.getByRole("button", { name: /cancel/i }).click();
    // Should navigate back (history.go(-1)); URL changes away from /agents/new
    await expect(page).not.toHaveURL(/\/agents\/new/);
  });
});

test.describe("AgentConfig — edit agent", () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.route("**/api/providers/", (route) =>
      route.fulfill({ json: PROVIDERS })
    );
    await page.route("**/api/workspaces/my-ws/agents/my-agent", (route) =>
      route.fulfill({ json: EXISTING_AGENT })
    );
    await page.goto("/workspaces/my-ws/agents/my-agent");
  });

  test("loads existing agent data into form fields", async ({
    authedPage: page,
  }) => {
    await expect(page.getByText(/edit agent: my-agent/i)).toBeVisible();
    await expect(page.locator("textarea")).toHaveValue(
      "You are a helpful assistant."
    );
  });

  test("name field is disabled in edit mode", async ({ authedPage: page }) => {
    await expect(page.locator('input[type="text"]').first()).toBeDisabled();
  });

  test("save sends PATCH and navigates to chat", async ({
    authedPage: page,
  }) => {
    await page.route(
      "**/api/workspaces/my-ws/agents/my-agent",
      async (route) => {
        if (route.request().method() === "PATCH") {
          await route.fulfill({ json: EXISTING_AGENT });
        } else {
          await route.fulfill({ json: EXISTING_AGENT });
        }
      }
    );
    await page.route("**/api/workspaces/my-ws", (route) =>
      route.fulfill({
        json: {
          name: "my-ws",
          agents: [EXISTING_AGENT],
          description: "",
          created_at: "",
          updated_at: "",
        },
      })
    );

    await page.locator("textarea").fill("Updated system prompt.");
    await page.getByRole("button", { name: /save agent/i }).click();

    await expect(page).toHaveURL(/\/workspaces\/my-ws\/chat/, {
      timeout: 5000,
    });
  });
});
