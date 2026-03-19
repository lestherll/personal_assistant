import { test, expect } from "@playwright/test";

test.describe("Chat flow", () => {
  test.skip(!!process.env.CI, "Requires a running LLM provider");

  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[type="text"]', "dev");
    await page.fill('input[type="password"]', "devpassword");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/workspaces");
  });

  test("send message shows streaming indicator then response", async ({ page }) => {
    // Navigate to default workspace chat
    await page.goto("/workspaces/default/chat");
    await page.waitForSelector('textarea');

    await page.fill('textarea', 'Hello');
    await page.keyboard.press('Enter');

    // Streaming cursor should appear
    await expect(page.locator('.animate-pulse')).toBeVisible({ timeout: 5000 });

    // After done, cursor disappears
    await expect(page.locator('.animate-pulse')).not.toBeVisible({ timeout: 30000 });

    // URL should update to include conversation id
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 5000 });
  });
});
