# Plugin Spec: p4cc-crawler

> **Status:** `beta` | **Version:** `1.0.2`

---

## Overview

p4cc-crawler is a web crawler and documentation extractor. It systematically explores websites — both static (curl-based) and SPAs (Playwright-based: Angular, React, Storybook) — filters discovered content by topic and keywords, downloads pages and attachments (PDF, DOC, XLS), converts them to Markdown, and generates a structured index with metrics.

Designed for intranet documentation extraction. Supports authenticated sites (Joomla, form-based, HTTP Basic) with automatic session re-authentication.

---

## Skill: `install`

### Purpose
Installs the `catalog.json` copy, then runs `check`.

### Invocation
```
/p4cc-crawler:install
```

### Non-Goals
- Does not install dependencies automatically

---

## Skill: `check`

### Purpose
Read-only verification of python3, curl (from catalog), pip packages beautifulsoup4 and html2text, the optional playwright (SPA mode) and the shipped scripts. Reports status and install instructions.

### Invocation
```
/p4cc-crawler:check
```

### Non-Goals
- Does not install dependencies automatically
- `check` never modifies anything

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
| 1.0.3 | Add `check` skill; `install` now creates folders/files and delegates verification to `check` |
| 1.0.2 | Add `extract` skill — full pipeline: configure, crawl, dedup, filter, download, generate |
| 1.0.1 | Initial release — `setup` skill |
