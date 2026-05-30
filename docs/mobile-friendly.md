# Mobile-friendly implementation notes

## Phase coverage

1. **Mobile shell**: below 780px, the sidebar becomes a compact header and bottom nav. Navigation stays reachable without scrolling, and very narrow phones switch the bottom nav to an icon-first layout to avoid label collisions.
2. **Ask-first workflow**: `/#ask` opens a single-surface chat experience. The library pane is hidden and the composer stays sticky above the safe-area-aware bottom nav.
3. **Library cards**: book rows wrap titles to two lines, expose metadata below the title, and avoid cramped desktop-only row behavior.
4. **Task-flow reshaping**: import, synthesis, settings, and mastery screens collapse into one-column mobile flows. Saved synthesis briefs become the primary surface on phones when a brief is available, while the form and history remain below it.
5. **Touch and typography**: shared controls use 44px to 48px targets, mobile padding tokens, safer text wrapping, and readable answer/source line heights. Long model IDs, citations, brief chips, and quiz answers wrap instead of forcing horizontal scroll.
6. **Frontend seams**: this kit keeps the code refactor intentionally shallow. It adds panel-state hooks and a mobile CSS layer without rewriting the whole 1,400-line `App.tsx` in one bite.
7. **Testing**: Node CSS assertions verify the mobile layer. Playwright smoke tests cover narrow phone, modern Android, and tablet breakpoints across Library, Ask, Import, Synthesis, Mastery, and Settings.

## Manual QA checklist

- At 320px width, no horizontal scrolling appears.
- Bottom nav shows Library, Ask, Import, Synthesis/Briefs, Mastery, and Settings/More.
- `/#ask` shows Ask the Czar first, with no library pane above it.
- Chat composer remains visible while scrolling through answers.
- Source excerpts are compact by default and readable when focused or hovered.
- Library cards allow two-line titles and readable metadata.
- Import and synthesis forms stack without clipped inputs.
- Saved synthesis briefs are readable before source evidence overwhelms the viewport.
- Quiz Previous, Next, and Submit controls remain reachable.
- Settings dropdowns tolerate long LM Studio model identifiers.
- Tablet breakpoint still feels like a tablet, not a shrunken desktop.
- Desktop two-pane layout remains intact.

## Automated checks

Run the static mobile CSS assertions:

```bash
cd frontend
npm run test:mobile-css
```

Run the Playwright mobile audit:

```bash
cd frontend
npm run test:mobile
```
