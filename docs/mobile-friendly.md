# Mobile-friendly implementation notes

## Phase coverage

1. **Mobile shell**: below 780px, the sidebar becomes a compact header and bottom nav. Navigation stays reachable without scrolling.
2. **Ask-first workflow**: `/#ask` opens a single-surface chat experience. The library pane is hidden and the composer stays sticky above the safe-area-aware bottom nav.
3. **Library cards**: book rows wrap titles to two lines, expose metadata below the title, and avoid cramped desktop-only row behavior.
4. **Task-flow reshaping**: import, synthesis, settings, and mastery screens collapse into one-column mobile flows. Quiz actions and chat composer remain sticky.
5. **Touch and typography**: shared controls use 44px to 48px targets, mobile padding tokens, safer text wrapping, and readable answer/source line heights.
6. **Frontend seams**: this kit keeps the code refactor intentionally shallow. It adds a panel seam for Ask and a mobile CSS layer without rewriting the whole 1,400-line `App.tsx` in one bite.
7. **Testing**: Node CSS assertions verify the mobile layer. Playwright smoke tests cover narrow phone, modern Android, and tablet breakpoints.

## Manual QA checklist

- At 320px width, no horizontal scrolling appears.
- Bottom nav shows Library, Ask, Import, Synthesis/Briefs, Mastery, and Settings/More.
- `/#ask` shows Ask the Czar first, with no library pane above it.
- Chat composer remains visible while scrolling through answers.
- Source excerpts are compact by default and readable when focused or hovered.
- Library cards allow two-line titles and readable metadata.
- Import and synthesis forms stack without clipped inputs.
- Quiz Previous, Next, and Submit controls remain reachable.
- Tablet breakpoint still feels like a tablet, not a shrunken desktop.
- Desktop two-pane layout remains intact.
