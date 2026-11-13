# Plugin Spec: p4cc-crawler

> **Status:** `beta` | **Version:** `1.0.6`

---

## Overview

p4cc-crawler is a web crawler and documentation extractor. It systematically explores websites — both static (curl-based) and SPAs (Playwright-based: Angular, React, Storybook) — filters discovered content by topic and keywords, downloads pages and attachments (PDF, DOC, XLS), converts them to Markdown, and generates a structured index with metrics.

Designed for intranet documentation extraction. Supports authenticated sites (Joomla, form-based, HTTP Basic) with automatic session re-authentication.

---

## Skill: `install`

### Purpose
Installs the marketplace `catalog.json` copy under `~/.p4cc/`. Idempotent. A real run is followed by `check`.

### Invocation
```
/p4cc-crawler:install [--dry-run] [--json] [--home DIR]
```

### Options
- `--dry-run` — resolves everything, **writes nothing**, prints the exact plan (`DRY|create|modify|<path>`) and ends with `RESUMEN|DRY|…` instead of `RESUMEN|OK|…`. Dry-run and real run share one code path.
- `--json` — machine-readable output. `--home DIR` — replaces `~` for `~/.p4cc/` (also `P4CC_HOME`).
- Exit codes: `0` ok · `1` failure · `2` bad usage · `3` precondition not met.

### Non-Goals
- Never installs external tools: `check` reports the command the person must run.
- Never writes another marketplace's `~/.p4cc/catalog.json` (it is left untouched and reported), nor the Claude Code cache.

---

## Skill: `check`

### Purpose
Read-only verification. Verifies `python3`, `curl`, the Python packages `beautifulsoup4` and `html2text`, the optional `playwright` (SPA mode, WARN when missing) and the five shipped scripts. Reports how to install anything missing.

### Invocation
```
/p4cc-crawler:check [--json] [--lines] [--home DIR]
```

### Output
- Default (script): one line per finding, `STATE|ID|detail` (`OK`, `INFO`, `WARN`, `FAIL`), then `RESUMEN|<n> FAIL|<m> WARN`. IDs are stable across versions: `folder-*`, `catalog-*`, `res-*`, `tool-*`, `pkg-*`, `ocr-lang-*`, `profile-*`.
- `--json` — `{plugin, skill, findings[{estado, id, detalle, componente}], summary{fail, warn}}`.
- Invoked as a skill without options it shows the human presentation (`--table`), fed by the same findings.
- Exit codes: `0` no failures · `1` failures · `2` bad usage · `3` precondition not met.

### Non-Goals
- Never creates, modifies or installs anything.
- Optional components (OCR, Playwright, `openpyxl`…) are WARN, never FAIL.

---

## Skill: `extract`

### Purpose
Orchestrates the full documentation extraction pipeline in 8 phases: configure (interactive), login (optional), crawl, deduplicate, filter, download, and generate. Produces a structured Markdown index (`INDEX.md`) with an extraction parameter table, page index, file directory tree, and process metrics.

### Invocation
```
/p4cc-crawler:extract
```

### Non-Goals
- Does not modify the crawled site
- Does not store credentials to disk — session memory only
- Does not support parallel crawling (sequential by design for rate-limiting compliance)

---

## Changelog

| Version | Changes |
|---------|---------|
| 1.0.6 | check: STATE\|ID\|detail output, --json, --table and exit codes from the shared check engine |
| 1.0.5 | install: add --dry-run, --json and --home; creates folders and the catalog copy through the shared check engine |
| 1.0.4 | `check`: raise python3 minimum to >=3.10.0 |
| 1.0.3 | Add `check` skill; `install` now creates folders/files and delegates verification to `check` |
| 1.0.2 | Add `extract` skill — full pipeline: configure, crawl, dedup, filter, download, generate |
| 1.0.1 | Initial release — `setup` skill |
