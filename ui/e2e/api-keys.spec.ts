import { test, expect } from "./fixtures";

const EXISTING_KEY = {
  id: "key-1",
  name: "my-key",
  key_prefix: "sk-abc",
  is_active: true,
  created_at: "2024-01-01T00:00:00Z",
  expires_at: null,
  last_used_at: null,
};

const CREATED_KEY = {
  id: "key-2",
  name: "new-key",
  key: "sk-xyz123secretvalue",
  key_prefix: "sk-xyz",
  is_active: true,
  created_at: "2024-01-02T00:00:00Z",
  expires_at: null,
  last_used_at: null,
};

test.describe("ApiKeys page", () => {
  test("shows empty state when no keys exist", async ({ authedPage: page }) => {
    await page.route("**/api/auth/api-keys", (route) =>
      route.fulfill({ json: [] })
    );
    await page.goto("/settings/api-keys");

    await expect(page.getByText(/no api keys yet/i)).toBeVisible();
    await expect(page.getByText(/programmatically/i)).toBeVisible();
  });

  test("create button is disabled when key name is empty", async ({
    authedPage: page,
  }) => {
    await page.route("**/api/auth/api-keys", (route) =>
      route.fulfill({ json: [] })
    );
    await page.goto("/settings/api-keys");

    await expect(page.getByRole("button", { name: /^create$/i })).toBeDisabled();
  });

  test("shows list of existing keys", async ({ authedPage: page }) => {
    await page.route("**/api/auth/api-keys", (route) =>
      route.fulfill({ json: [EXISTING_KEY] })
    );
    await page.goto("/settings/api-keys");

    await expect(page.getByText("my-key")).toBeVisible();
    await expect(page.getByText(/sk-abc/)).toBeVisible();
    await expect(page.getByRole("button", { name: /revoke/i })).toBeVisible();
  });

  test("creating a key reveals it once with a copy button", async ({
    authedPage: page,
  }) => {
    let keys: object[] = [];

    await page.route("**/api/auth/api-keys", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: keys });
      } else {
        keys = [{ ...CREATED_KEY, key: undefined }];
        await route.fulfill({ json: CREATED_KEY, status: 201 });
      }
    });

    await page.goto("/settings/api-keys");

    await page.fill('input[placeholder*="Key name"]', "new-key");
    await page.getByRole("button", { name: /^create$/i }).click();

    // Raw key banner should appear
    await expect(page.getByText(/shown once/i)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("sk-xyz123secretvalue")).toBeVisible();
    await expect(page.getByRole("button", { name: /copy/i })).toBeVisible();
  });

  test("dismissing the key banner hides it", async ({ authedPage: page }) => {
    await page.route("**/api/auth/api-keys", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: [] });
      } else {
        await route.fulfill({ json: CREATED_KEY, status: 201 });
      }
    });

    await page.goto("/settings/api-keys");
    await page.fill('input[placeholder*="Key name"]', "new-key");
    await page.getByRole("button", { name: /^create$/i }).click();

    await expect(page.getByText(/shown once/i)).toBeVisible();
    await page.getByText(/i've copied this key/i).click();

    await expect(page.getByText(/shown once/i)).not.toBeVisible();
    await expect(page.getByText("sk-xyz123secretvalue")).not.toBeVisible();
  });

  test("revoking a key removes it from the active list", async ({
    authedPage: page,
  }) => {
    let keys = [EXISTING_KEY];

    await page.route("**/api/auth/api-keys", (route) =>
      route.fulfill({ json: keys })
    );
    await page.route(`**/api/auth/api-keys/${EXISTING_KEY.id}`, async (route) => {
      if (route.request().method() === "DELETE") {
        keys = [{ ...EXISTING_KEY, is_active: false }];
        await route.fulfill({ status: 204, body: "" });
      }
    });

    await page.goto("/settings/api-keys");
    await expect(page.getByText("my-key")).toBeVisible();

    page.on("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: /revoke/i }).click();

    // Revoke button disappears (key is now inactive)
    await expect(page.getByRole("button", { name: /revoke/i })).not.toBeVisible();
    await expect(page.getByText(/revoked/i)).toBeVisible();
  });
});
