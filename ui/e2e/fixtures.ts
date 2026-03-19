import { test as base, type Page } from "@playwright/test";

export const TEST_USER = {
  id: "00000000-0000-0000-0000-000000000001",
  username: "testuser",
  email: "test@example.com",
  created_at: "2024-01-01T00:00:00Z",
};

export const TOKENS = {
  access_token: "fake-access-token",
  refresh_token: "fake-refresh-token",
};

/**
 * Call before page.goto() to simulate a logged-in session.
 * Sets refresh_token in localStorage and mocks the refresh, me, and sidebar
 * background requests so tests don't need to handle them individually.
 */
export async function mockAuth(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("refresh_token", "fake-refresh-token");
  });
  await page.route("**/api/auth/refresh", (route) =>
    route.fulfill({ json: TOKENS })
  );
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({ json: TEST_USER })
  );
  // Sidebar always fetches the workspace list — provide an empty default.
  // Tests that need specific workspaces register their own handler which takes
  // priority (Playwright applies route handlers LIFO).
  await page.route("**/api/workspaces/", (route) =>
    route.fulfill({ json: [] })
  );
  // Sidebar fetches recent conversations when a workspace name param is present.
  // Use ** to match any workspace name and any query string (e.g. ?limit=20).
  await page.route("**/api/workspaces/*/conversations**", (route) => {
    // Only handle sidebar's GET — let tests override with their own handler.
    if (route.request().method() === "GET") {
      route.fulfill({ json: [] });
    } else {
      route.continue();
    }
  });
}

export const test = base.extend<{ authedPage: Page }>({
  authedPage: async ({ page }, use) => {
    await mockAuth(page);
    await use(page);
  },
});

export { expect } from "@playwright/test";
