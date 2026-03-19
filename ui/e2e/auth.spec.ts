import { test, expect } from "@playwright/test";
import { mockAuth, TOKENS, TEST_USER } from "./fixtures";

test.describe("Auth — login", () => {
  test("valid credentials navigate to /workspaces", async ({ page }) => {
    await page.route("**/api/auth/login", (route) =>
      route.fulfill({ json: TOKENS })
    );
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({ json: TEST_USER })
    );
    // Stub workspaces list so the page doesn't hang
    await page.route("**/api/workspaces/", (route) =>
      route.fulfill({ json: [] })
    );

    await page.goto("/login");
    await page.fill('input[name="username"]', "testuser");
    await page.fill('input[name="password"]', "correctpass");
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(/\/workspaces/, { timeout: 5000 });
  });

  test("invalid credentials show an error message", async ({ page }) => {
    await page.route("**/api/auth/login", (route) =>
      route.fulfill({
        status: 401,
        json: { detail: "Invalid credentials" },
      })
    );

    await page.goto("/login");
    await page.fill('input[name="username"]', "testuser");
    await page.fill('input[name="password"]', "wrongpass");
    await page.click('button[type="submit"]');

    await expect(page.getByText(/error 401/i)).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Auth — protected routes", () => {
  test("unauthenticated visit to /workspaces redirects to /login", async ({
    page,
  }) => {
    // Fresh context — no refresh_token in localStorage.
    // AuthContext will immediately dispatch CLEAR, ProtectedRoute redirects.
    await page.goto("/workspaces");
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });
});

test.describe("Auth — register tab", () => {
  test("switching to register tab shows email field", async ({ page }) => {
    await page.goto("/login");
    await page.click("text=Register");
    await expect(page.locator('input[name="email"]')).toBeVisible();
  });
});
