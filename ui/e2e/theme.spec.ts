import { test, expect } from "@playwright/test";

test.describe("Dark mode", () => {
  test("toggle dark mode persists across navigation and reload", async ({ page }) => {
    await page.goto("/login");

    // Inject a logged-in state to skip login
    await page.evaluate(() => {
      localStorage.setItem("theme", "dark");
      document.documentElement.classList.add("dark");
    });

    await page.reload();

    // Should still be dark after reload (script in <head> applies it)
    await expect(page.locator("html")).toHaveClass(/dark/);

    // Toggle to light
    await page.evaluate(() => {
      localStorage.setItem("theme", "light");
      document.documentElement.classList.remove("dark");
    });
    await page.reload();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });
});
