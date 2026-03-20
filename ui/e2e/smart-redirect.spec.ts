import { test, expect, type Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Shared test data
// ---------------------------------------------------------------------------

const USER = { id: "user-1", username: "testuser", email: "test@example.com" };

const WS = {
  id: "ws-1",
  name: "my-workspace",
  description: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-03-19T12:00:00Z",
};

const CONV = {
  id: "conv-abc123",
  title: "Test conversation",
  created_at: "2026-03-19T10:00:00Z",
  updated_at: "2026-03-19T11:00:00Z",
};

const TOKENS = {
  access_token: "test-access",
  refresh_token: "test-refresh",
  token_type: "bearer",
};

// ---------------------------------------------------------------------------
// Route mock helpers
// ---------------------------------------------------------------------------

async function mockLoginEndpoints(page: Page) {
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(TOKENS),
    }),
  );
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(USER),
    }),
  );
}

async function mockRefreshEndpoints(page: Page) {
  await page.route("**/api/auth/refresh", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...TOKENS, refresh_token: "new-test-refresh" }),
    }),
  );
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(USER),
    }),
  );
}

async function mockWorkspaceList(page: Page, workspaces: object[]) {
  await page.route("**/api/workspaces/", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(workspaces),
    }),
  );
}

async function mockConversations(
  page: Page,
  workspaceName: string,
  conversations: object[],
) {
  await page.route(
    new RegExp(`/api/workspaces/${workspaceName}/conversations`),
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(conversations),
      }),
  );
}

/** Fill and submit the login form. Routes must be set up before calling this. */
async function submitLogin(page: Page) {
  await page.goto("/login");
  await page.fill('input[name="username"]', "testuser");
  await page.fill('input[name="password"]', "testpassword");
  await page.click('button[type="submit"]');
}

/**
 * Inject a fake refresh token into localStorage so the app treats the session
 * as authenticated on next load. Navigate to a page first so localStorage is
 * accessible, then navigate to the target URL.
 */
async function goToAsAuthenticated(page: Page, url: string) {
  await page.goto("/login"); // load the app bundle first
  await page.evaluate(() => {
    localStorage.setItem("refresh_token", "existing-refresh-token");
  });
  await page.goto(url);
}

// ---------------------------------------------------------------------------
// Tests: login → smart redirect
// ---------------------------------------------------------------------------

test.describe("Smart redirect after login", () => {
  test("redirects to most recent conversation when workspace and conversation exist", async ({
    page,
  }) => {
    await mockLoginEndpoints(page);
    await mockWorkspaceList(page, [WS]);
    await mockConversations(page, WS.name, [CONV]);

    await submitLogin(page);

    await expect(page).toHaveURL(
      `/workspaces/${WS.name}/chat/${CONV.id}`,
      { timeout: 5000 },
    );
  });

  test("redirects to new chat when workspace exists but has no conversations", async ({
    page,
  }) => {
    await mockLoginEndpoints(page);
    await mockWorkspaceList(page, [WS]);
    await mockConversations(page, WS.name, []);

    await submitLogin(page);

    await expect(page).toHaveURL(`/workspaces/${WS.name}/chat`, {
      timeout: 5000,
    });
  });

  test("redirects to workspace list when user has no workspaces", async ({
    page,
  }) => {
    await mockLoginEndpoints(page);
    await mockWorkspaceList(page, []);

    await submitLogin(page);

    await expect(page).toHaveURL("/workspaces", { timeout: 5000 });
  });

  test("picks the most recently updated workspace when multiple exist", async ({
    page,
  }) => {
    await mockLoginEndpoints(page);

    const olderWs = {
      ...WS,
      id: "ws-old",
      name: "old-workspace",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const newerWs = {
      ...WS,
      id: "ws-new",
      name: "new-workspace",
      updated_at: "2026-03-19T12:00:00Z",
    };

    // Return older workspace first to confirm the client sorts by updated_at
    await mockWorkspaceList(page, [olderWs, newerWs]);
    await mockConversations(page, newerWs.name, []);

    await submitLogin(page);

    await expect(page).toHaveURL(`/workspaces/${newerWs.name}/chat`, {
      timeout: 5000,
    });
  });

  test("falls back to workspace list when workspace API call fails", async ({
    page,
  }) => {
    await mockLoginEndpoints(page);
    await page.route("**/api/workspaces/", (route) =>
      route.fulfill({ status: 500, body: "Internal server error" }),
    );

    await submitLogin(page);

    await expect(page).toHaveURL("/workspaces", { timeout: 5000 });
  });
});

// ---------------------------------------------------------------------------
// Tests: register → smart redirect
// ---------------------------------------------------------------------------

test.describe("Smart redirect after register", () => {
  test("redirects to workspace chat when default workspace has no conversations", async ({
    page,
  }) => {
    await page.route("**/api/auth/register", (route) =>
      route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ user: USER, tokens: TOKENS }),
      }),
    );
    await mockWorkspaceList(page, [WS]);
    await mockConversations(page, WS.name, []);

    await page.goto("/login");
    await page.click("text=Register");
    await page.fill('input[name="username"]', "newuser");
    await page.fill('input[name="email"]', "new@example.com");
    await page.fill('input[name="password"]', "testpassword123");
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(`/workspaces/${WS.name}/chat`, {
      timeout: 5000,
    });
  });

  test("redirects to most recent conversation after register when one exists", async ({
    page,
  }) => {
    await page.route("**/api/auth/register", (route) =>
      route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ user: USER, tokens: TOKENS }),
      }),
    );
    await mockWorkspaceList(page, [WS]);
    await mockConversations(page, WS.name, [CONV]);

    await page.goto("/login");
    await page.click("text=Register");
    await page.fill('input[name="username"]', "newuser");
    await page.fill('input[name="email"]', "new@example.com");
    await page.fill('input[name="password"]', "testpassword123");
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(
      `/workspaces/${WS.name}/chat/${CONV.id}`,
      { timeout: 5000 },
    );
  });
});

// ---------------------------------------------------------------------------
// Tests: index route (/) → smart redirect for already-authenticated users
// ---------------------------------------------------------------------------

test.describe("Smart redirect on index route", () => {
  test("redirects to most recent conversation when already authenticated", async ({
    page,
  }) => {
    await mockRefreshEndpoints(page);
    await mockWorkspaceList(page, [WS]);
    await mockConversations(page, WS.name, [CONV]);

    await goToAsAuthenticated(page, "/");

    await expect(page).toHaveURL(
      `/workspaces/${WS.name}/chat/${CONV.id}`,
      { timeout: 5000 },
    );
  });

  test("redirects to new chat when authenticated but no prior conversations", async ({
    page,
  }) => {
    await mockRefreshEndpoints(page);
    await mockWorkspaceList(page, [WS]);
    await mockConversations(page, WS.name, []);

    await goToAsAuthenticated(page, "/");

    await expect(page).toHaveURL(`/workspaces/${WS.name}/chat`, {
      timeout: 5000,
    });
  });

  test("redirects to workspace list when authenticated but no workspaces", async ({
    page,
  }) => {
    await mockRefreshEndpoints(page);
    await mockWorkspaceList(page, []);

    await goToAsAuthenticated(page, "/");

    await expect(page).toHaveURL("/workspaces", { timeout: 5000 });
  });

  test("redirects to login when not authenticated", async ({ page }) => {
    // No refresh token in localStorage — fresh session
    await page.goto("/");
    await expect(page).toHaveURL("/login", { timeout: 5000 });
  });
});
