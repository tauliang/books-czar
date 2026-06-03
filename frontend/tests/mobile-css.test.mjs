import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const __dirname = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(__dirname, "../src/styles.mobile.css"), "utf8");

function expectCss(fragment) {
  assert.ok(css.includes(fragment), `Expected mobile CSS to include: ${fragment}`);
}

test("defines mobile design tokens and touch targets", () => {
  expectCss("--tap-target: 48px");
  expectCss("--mobile-page-padding: 12px");
  expectCss("--mobile-nav-height: 76px");
  expectCss("min-height: var(--tap-target)");
  expectCss("min-width: var(--tap-target)");
});

test("installs mobile app shell and bottom navigation", () => {
  expectCss("@media (max-width: 780px)");
  expectCss(".appShell");
  expectCss("padding-bottom: calc(var(--mobile-nav-height) + env(safe-area-inset-bottom))");
  expectCss(".panelTabs");
  expectCss("grid-template-columns: repeat(6, minmax(0, 1fr))");
  expectCss("bottom: 0");
});

test("turns library rows into readable cards on phones", () => {
  expectCss(".bookRow");
  expectCss("-webkit-line-clamp: 2");
  expectCss(".bookStats");
  expectCss("grid-column: 1 / -1");
});

test("adds mobile-first ask workflow", () => {
  expectCss('.appShell[data-panel="ask"] .workspace');
  expectCss('.appShell[data-panel="ask"] .libraryPane');
  expectCss(".chatComposer");
  expectCss("position: sticky");
  expectCss("bottom: calc(var(--mobile-nav-height) + env(safe-area-inset-bottom))");
});

test("keeps dense evidence readable instead of overwhelming the viewport", () => {
  expectCss(".source p");
  expectCss("-webkit-line-clamp: 4");
  expectCss("overflow-wrap: anywhere");
});

test("hardens narrow navigation and metadata wrapping", () => {
  expectCss("@media (max-width: 360px)");
  expectCss("font-size: 0");
  expectCss(".briefGlanceChips span");
  expectCss("min-width: min(100%, 9rem)");
  expectCss(".settingsForm select");
  expectCss("text-overflow: ellipsis");
});

test("promotes saved synthesis briefs on mobile when a brief is available", () => {
  expectCss('[data-has-synthesis="true"] .chatPane');
  expectCss("order: -1");
});

test("keeps non-chat mobile panels to one main surface", () => {
  expectCss('.appShell[data-panel="library"] .chatPane');
  expectCss('.appShell[data-panel="import"] .chatPane');
  expectCss('.appShell[data-panel="settings"] .chatPane');
});
