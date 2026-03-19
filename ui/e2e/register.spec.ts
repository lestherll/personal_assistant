import { test, expect } from "@playwright/test";

test.describe("Registration flow", () => {
  test("register new user auto-redirects to workspaces", async ({ page }) => {
    const username = `testuser_${Date.now()}`;

    await page.goto("/login");

    // Switch to Register tab
    await page.click("text=Register");

    await page.fill('input[name="username"]', username);
    await page.fill('input[name="email"]', `${username}@example.com`);
    await page.fill('input[name="password"]', "testpassword123");
    await page.click('button[type="submit"]');

    // Should land on workspaces after successful registration
    await expect(page).toHaveURL(/\/workspaces/, { timeout: 10000 });
  });
});
