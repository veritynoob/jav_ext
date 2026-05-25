# JAV Ext

## HTMX templates

Pages with filtering/sorting/pagination split into two templates: `<name>.html` extends `base.html` and includes `<name>_content.html`; `<name>_content.html` has just controls+data, no base extension. Routes return the content template for `HX-Request` headers, full template otherwise.

**Why:** HTMX swaps target `#main`. Returning a full page nests chrome inside chrome.

## Database

- SQLite at `data/jav.db`
- `save_magnets` uses `INSERT OR IGNORE` to deduplicate individual magnets

## Subagent dispatch

1. **One review for mechanical tasks** — two-stage (spec+quality) only when design ambiguity or multi-file integration.
2. **Prompt ≤200 words** — task text only, 2-3 sentences context, no previous results.
3. **Extract once** — read the plan once, pull all task texts. Never re-read.
4. **Batch tiny tasks** — adjacent, <10 lines each, independent → single dispatch.

**Why:** 3 subagents/task compounds with 5+ tasks, causing visible slowdown by task 3-4.
