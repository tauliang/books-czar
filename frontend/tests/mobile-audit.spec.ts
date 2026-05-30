import { expect, test, type Page } from "@playwright/test";

const now = "2026-06-03T12:00:00.000Z";

async function stubApi(page: Page) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body)
      });

    if (path === "/api/books") {
      return json([
        {
          id: "book-1",
          title: "A Very Long Executive Guide To Local Artificial Intelligence Operating Models",
          author: "Books Czar",
          source: "upload",
          source_url: null,
          file_name: "ai-operating-models.pdf",
          file_format: "pdf",
          status: "indexed",
          note: null,
          created_at: now,
          updated_at: now,
          chunk_count: 42
        }
      ]);
    }
    if (path === "/api/health") {
      return json({
        ok: true,
        lmstudio_ok: true,
        lmstudio_message: "LM Studio online",
        book_count: 1,
        chunk_count: 42
      });
    }
    if (path === "/api/settings") {
      return json({
        lmstudio_base_url: "http://127.0.0.1:1234/v1",
        chat_model: "local-model",
        embedding_model: "text-embedding-nomic-embed-text-v1.5-with-a-long-local-model-id",
        chunk_size: 1800,
        chunk_overlap: 240
      });
    }
    if (path === "/api/models") {
      return json({
        ok: true,
        message: "Models loaded",
        models: [
          "glm-5.0",
          "text-embedding-nomic-embed-text-v1.5-with-a-long-local-model-id"
        ],
        chat_model: "local-model",
        embedding_model: "text-embedding-nomic-embed-text-v1.5-with-a-long-local-model-id"
      });
    }
    if (path === "/api/syntheses" || path === "/api/syntheses/syn-1") {
      const run = {
        id: "syn-1",
        title: "Mobile Board Brief With A Long But Readable Title",
        objective: "What should executives prioritize?",
        audience: "c_suite",
        lens: "strategy",
        book_ids: ["book-1"],
        status: "complete",
        markdown:
          "# Board Brief\n\n## Executive Takeaway\nLocal AI operating models need clear ownership. [S1]\n\n## Recommended 30/60/90 Day Actions\n30 days\nMap current accountability.\n\n60 days\nSet governance forums.\n\n90 days\nReview measurable adoption.\n\n## Metrics to Watch\nDecision latency, reuse, risk exceptions. [S1]",
        sources: [
          {
            book_id: "book-1",
            title: "A Very Long Executive Guide To Local Artificial Intelligence Operating Models",
            location: "chapter 1",
            excerpt: "A long source excerpt that should wrap on mobile without forcing horizontal overflow.",
            score: 0.91
          }
        ],
        error: null,
        created_at: now,
        updated_at: now
      };
      return json(path === "/api/syntheses" ? [run] : run);
    }
    if (path === "/api/quizzes" || path === "/api/quizzes/quiz-1") {
      const quiz = {
        id: "quiz-1",
        title: "Executive AI Mastery Quiz",
        book_ids: ["book-1"],
        question_count: 5,
        passing_score: 80,
        status: "complete",
        questions: [
          {
            id: "q1",
            prompt: "Which operating model concern should executives resolve first?",
            choices: [
              { id: "A", text: "Clear ownership" },
              { id: "B", text: "A decorative dashboard" },
              { id: "C", text: "Unscoped pilots" },
              { id: "D", text: "Delayed governance" }
            ],
            citations: ["S1"]
          }
        ],
        error: null,
        created_at: now,
        updated_at: now
      };
      return json(path === "/api/quizzes" ? [quiz] : quiz);
    }
    if (path === "/api/quizzes/quiz-1/attempts") {
      return json([]);
    }
    return json({});
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

async function expectMobileChrome(page: Page) {
  await expect(page.locator(".panelTabs")).toBeVisible();
  await expect(page.getByRole("button", { name: "Library", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Settings", exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);
}

async function expectPrimaryActionVisible(page: Page, name: RegExp) {
  const action = page.getByRole("button", { name });
  await expect(action).toBeVisible();
  const box = await action.boundingBox();
  expect(box?.width ?? 0).toBeGreaterThanOrEqual(44);
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
}

test.describe("mobile layout", () => {
  test.beforeEach(async ({ page }) => {
    await stubApi(page);
  });

  test("renders the compact shell with bottom navigation", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".appShell")).toBeVisible();
    await expectMobileChrome(page);
  });

  test("opens Ask as a single mobile surface with a sticky composer", async ({ page }) => {
    await page.goto("/#ask");
    await expect(page.locator('.appShell[data-panel="ask"]')).toBeVisible();
    await expect(page.locator(".chatHeader")).toContainText("Ask the Czar");
    await expect(page.locator(".libraryPane")).toBeHidden();
    await expect(page.locator(".chatComposer")).toBeVisible();

    const composerPosition = await page.locator(".chatComposer").evaluate((element) => getComputedStyle(element).position);
    expect(["sticky", "fixed"]).toContain(composerPosition);
    await expectMobileChrome(page);
  });

  test("keeps Library readable as cards on narrow screens", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".libraryPane")).toBeVisible();
    await expect(page.locator(".toolbar")).toBeVisible();
    await expectPrimaryActionVisible(page, /index/i);
    await expectMobileChrome(page);
  });

  test("stacks Import controls without clipping primary actions", async ({ page }) => {
    await page.goto("/#import");
    await expect(page.locator('.appShell[data-panel="import"]')).toBeVisible();
    await expect(page.locator(".importGrid")).toBeVisible();
    await expectPrimaryActionVisible(page, /scan \.\/books/i);
    await expectPrimaryActionVisible(page, /download authorized urls/i);
    await expectMobileChrome(page);
  });

  test("keeps Synthesis usable as form, history, and brief surfaces", async ({ page }) => {
    await page.goto("/#synthesis");
    await expect(page.locator('.appShell[data-panel="synthesis"]')).toBeVisible();
    await expect(page.locator(".synthesisForm")).toBeVisible();
    await expect(page.locator(".historyPanel")).toBeVisible();
    await expect(page.locator(".synthesisDetail")).toBeVisible();
    await expectPrimaryActionVisible(page, /generate brief/i);
    await expectMobileChrome(page);
  });

  test("keeps Mastery quiz controls reachable on mobile", async ({ page }) => {
    await page.goto("/#mastery");
    await expect(page.locator('.appShell[data-panel="mastery"]')).toBeVisible();
    await expect(page.locator(".synthesisForm")).toBeVisible();
    await expect(page.locator(".synthesisDetail")).toBeVisible();
    await expect(page.getByLabel(/learner name/i)).toBeVisible();
    await expectPrimaryActionVisible(page, /generate quiz/i);
    await expectMobileChrome(page);
  });

  test("keeps Settings model controls readable on mobile", async ({ page }) => {
    await page.goto("/#settings");
    await expect(page.locator('.appShell[data-panel="settings"]')).toBeVisible();
    await expect(page.getByLabel(/lm studio url/i)).toBeVisible();
    await expect(page.getByLabel(/chat model/i)).toBeVisible();
    await expect(page.getByLabel(/embedding model/i)).toBeVisible();
    await expectPrimaryActionVisible(page, /save settings/i);
    await expectMobileChrome(page);
  });
});
