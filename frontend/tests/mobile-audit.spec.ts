import { expect, test, type Page } from "@playwright/test";

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test.describe("mobile layout", () => {
  test("renders the compact shell with bottom navigation", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".appShell")).toBeVisible();
    await expect(page.locator(".panelTabs")).toBeVisible();
    await expect(page.getByRole("button", { name: /ask/i })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("opens Ask as a single mobile surface with a sticky composer", async ({ page }) => {
    await page.goto("/#ask");
    await expect(page.locator('.appShell[data-panel="ask"]')).toBeVisible();
    await expect(page.locator(".chatHeader")).toContainText("Ask the Czar");
    await expect(page.locator(".libraryPane")).toBeHidden();
    await expect(page.locator(".chatComposer")).toBeVisible();

    const composerPosition = await page.locator(".chatComposer").evaluate((element) => getComputedStyle(element).position);
    expect(["sticky", "fixed"]).toContain(composerPosition);
    await expectNoHorizontalOverflow(page);
  });

  test("keeps Library readable as cards on narrow screens", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".libraryPane")).toBeVisible();
    await expect(page.locator(".toolbar")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});
