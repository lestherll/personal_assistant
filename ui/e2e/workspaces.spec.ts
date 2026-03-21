import { test, expect } from "./fixtures";

const WORKSPACE_A = {
  name: "my-workspace",
  description: "Test workspace",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};
const WORKSPACE_B = {
  name: "another-workspace",
  description: "",
  created_at: "2024-01-02T00:00:00Z",
  updated_at: "2024-01-02T00:00:00Z",
};

test.describe("WorkspaceList page", () => {
  test("shows list of workspaces from API", async ({ authedPage: page }) => {
    await page.route("**/api/workspaces/", (route) =>
      route.fulfill({ json: [WORKSPACE_A, WORKSPACE_B] })
    );
    await page.goto("/workspaces");

    // Scope to main to avoid matching Sidebar nav links too
    const main = page.locator("main");
    await expect(main.getByRole("link", { name: "my-workspace" })).toBeVisible();
    await expect(main.getByRole("link", { name: "another-workspace" })).toBeVisible();
  });

  test("shows empty state when no workspaces exist", async ({ authedPage: page }) => {
    // fixture already mocks /api/workspaces/ with []
    await page.goto("/workspaces");

    await expect(page.getByText(/no workspaces yet/i)).toBeVisible();
  });

  test("create button is disabled when name is empty", async ({
    authedPage: page,
  }) => {
    await page.goto("/workspaces");

    const createBtn = page.getByRole("button", { name: /create workspace/i });
    await expect(createBtn).toBeDisabled();
  });

  test("create workspace adds it to the list", async ({ authedPage: page }) => {
    let workspaceList = [WORKSPACE_A];

    await page.route("**/api/workspaces/", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: workspaceList });
      } else {
        workspaceList = [...workspaceList, WORKSPACE_B];
        await route.fulfill({ json: WORKSPACE_B, status: 201 });
      }
    });
    // Stub default agent creation (best-effort)
    await page.route("**/api/workspaces/another-workspace/agents/", (route) =>
      route.fulfill({ status: 201, json: {} })
    );

    await page.goto("/workspaces");
    const main = page.locator("main");
    await expect(main.getByRole("link", { name: "my-workspace" })).toBeVisible();

    await page.fill('input[placeholder*="Name"]', "another-workspace");
    await page.getByRole("button", { name: /create workspace/i }).click();

    await expect(main.getByRole("link", { name: "another-workspace" })).toBeVisible();
  });

  test("delete workspace removes it from the list after confirm", async ({
    authedPage: page,
  }) => {
    let workspaceList = [WORKSPACE_A];

    await page.route("**/api/workspaces/", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: workspaceList });
      } else {
        await route.continue();
      }
    });
    await page.route(`**/api/workspaces/${WORKSPACE_A.name}`, async (route) => {
      if (route.request().method() === "DELETE") {
        workspaceList = [];
        await route.fulfill({ status: 204, body: "" });
      }
    });

    await page.goto("/workspaces");
    const main = page.locator("main");
    await expect(main.getByRole("link", { name: "my-workspace" })).toBeVisible();

    // First click opens inline confirmation row
    await page.getByRole("button", { name: /delete/i }).first().click();
    // Second click confirms the delete
    await page.getByRole("button", { name: /delete/i }).first().click();

    await expect(main.getByText(/no workspaces yet/i)).toBeVisible();
  });
});

test.describe("WorkspaceList — navigation", () => {
  test("History link points to conversations page", async ({ authedPage: page }) => {
    await page.route("**/api/workspaces/", (route) =>
      route.fulfill({ json: [WORKSPACE_A] })
    );
    await page.goto("/workspaces");

    const historyLink = page.locator("main").getByRole("link", { name: /history/i });
    await expect(historyLink).toHaveAttribute(
      "href",
      `/workspaces/${WORKSPACE_A.name}/conversations`
    );
  });
});
