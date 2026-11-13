# Plugin Spec: p4cc-ccvv

> **Status:** `beta` | **Version:** `1.0.20`

---

## Overview

AI-powered CV generation and management system. Extracts structured profile data from existing CVs, adapts content to specific job offers, and exports to multiple formats. Supports multiple users with isolated profile storage.

All data is stored globally at `~/.p4cc/p4cc-ccvv/` following the p4cc-* scope convention.

---

## Skill: `install`

### Purpose
Creates `~/.p4cc/`, `~/.p4cc/p4cc-ccvv/profiles/` and installs the marketplace `catalog.json` copy. Idempotent. A real run is followed by `check`.

### Invocation
```
/p4cc-ccvv:install [--dry-run] [--json] [--home DIR]
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
Read-only verification. Verifies the storage folders (and `input/`, `data/`, `output/` of each profile), the shipped templates and schemas, and `pandoc`, `pdflatex`, `python3`. Reports how to install anything missing.

### Invocation
```
/p4cc-ccvv:check [--json] [--lines] [--home DIR]
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

## Skill: `profile-gather`

### Purpose
Reads a source CV file (PDF/DOCX) from the user's `input/` folder and extracts structured data into `profile.json` following the profile schema.

### Invocation
```
/p4cc-ccvv:profile-gather
```

### Non-Goals
- Does not modify existing profile data (use `profile-update` instead)
- Does not generate CVs

---

## Skill: `profile-update`

### Purpose
Updates an existing `profile.json` with new or corrected data. Supports document-based and interactive modes. Always creates a timestamped backup.

### Invocation
```
/p4cc-ccvv:profile-update
```

---

## Skill: `generate`

### Purpose
Generates a new CV draft adapted to a specific job position. Optionally analyzes a job offer to extract keywords and tailor content. Produces an editable markdown draft.

### Invocation
```
/p4cc-ccvv:generate
```

### Output
- `CV-[id]-META-[slug]-CV.md` — editable CV draft
- `CV-[id]-META-[slug]-LETTER.md` — cover letter (optional)

---

## Skill: `regen`

### Purpose
Regenerates an existing CV draft using updated profile data. Preserves original job parameters (position, offer analysis, keywords).

### Invocation
```
/p4cc-ccvv:regen
```

---

## Skill: `export`

### Purpose
Converts a CV draft to a final output format (PDF, DOCX, HTML, MD) in the selected language using Pandoc.

### Invocation
```
/p4cc-ccvv:export
```

### Output
`CV-[id]-[export_id]-[slug]-CV.[format]`

### Supported formats
`pdf`, `docx`, `html`, `md`

### Supported languages
`es` (Español), `en` (English), `fr` (Français), `de` (Deutsch), `it` (Italiano), `pt` (Português)

---

## Changelog

| Version | Changes |
|---------|---------|
| 1.0.20 | check: STATE\|ID\|detail output, --json, --table and exit codes from the shared check engine |
| 1.0.19 | install: add --dry-run, --json and --home; creates folders and the catalog copy through the shared check engine |
| 1.0.16 | setup: add plugin dep check with unified type table |
| 1.0.15 | setup: read dependencies[] instead of requires[] |
| 1.0.14 | profile-gather: photo detection from input/; generate: dual templates, DIGITAL IDENTITY section, 6-language label translation |
| 1.0.12 | profile-gather+profile-update: social networks y repositorios profesionales |
| 1.0.10 | generate: Reescritura completa: optimización ATS/AI >95% |
| 1.0.9 | generate: añade Step 4b que adapta info.titles al puesto objetivo antes de generar el CV, en lugar de copiar los títulos del perfil verbatim |
| 1.0.8 | profile-gather: solicita al usuario una ruta donde encontrar un fichero de cv y una foto, adicionalmente el skill debe copiarla a la carpeta de datos del profile y preguntar si la elimina del origen (puesto que ya esta copiada en el storage del plugin) |
| 1.0.7 | export: sugerir 1: copiar fichero exportado a cwd, copiar fichero exportado a otro path, no copiar |
| 1.0.18 | `check`: raise python3 minimum to >=3.10.0 |
| 1.0.17 | Add `check` skill; `install` now creates folders/files and delegates verification to `check` |
| 1.0.6 | Initial release with 6 skills |
