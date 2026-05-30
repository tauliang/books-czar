import assert from "node:assert/strict";
import test from "node:test";

import {
  cleanMarkdown,
  parseBriefMarkdown,
  presentableLines,
} from "../.test-build/briefParser.js";

test("parseBriefMarkdown extracts takeaway, actions, and metrics", () => {
  const parsed = parseBriefMarkdown(`# Board Brief: AI Strategy

## Executive Takeaway
Leaders should prioritize **private evidence-backed AI** [S1].

## Recommended 30/60/90 Day Actions
- 30 days: Confirm priority sources [S1].
- 60 days: Operationalize governance [S2].

## Metrics to Watch
- Research cycle time [S1].
- Citation coverage [S2].
`);

  assert.equal(parsed.title, "Board Brief: AI Strategy");
  assert.deepEqual(parsed.takeaway, ["Leaders should prioritize private evidence-backed AI [S1]."]);
  assert.equal(parsed.actions?.title, "Recommended 30/60/90 Day Actions");
  assert.deepEqual(presentableLines(parsed.actions?.lines ?? []), [
    "30 days: Confirm priority sources [S1].",
    "60 days: Operationalize governance [S2].",
  ]);
  assert.deepEqual(presentableLines(parsed.metrics?.lines ?? []), [
    "Research cycle time [S1].",
    "Citation coverage [S2].",
  ]);
});

test("parseBriefMarkdown keeps plain fallback text readable", () => {
  const parsed = parseBriefMarkdown("A compact brief without headings.");

  assert.equal(parsed.title, "Synthesis Brief");
  assert.equal(parsed.sections[0].title, "Summary");
  assert.deepEqual(presentableLines(parsed.sections[0].lines), ["A compact brief without headings."]);
});

test("cleanMarkdown removes lightweight markdown markers", () => {
  assert.equal(cleanMarkdown("**Metric:** `cycle time`"), "Metric: cycle time");
});
