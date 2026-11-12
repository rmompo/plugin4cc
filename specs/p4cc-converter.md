# Plugin Spec: p4cc-converter

> **Status:** `beta` | **Version:** `1.0.10`

---

## Overview

`p4cc-converter` converts PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX and XLSM documents to structured, LLM-optimized Markdown. It uses a local pipeline driven by three external tools (`qpdf`, `python3`, `libreoffice`), optional OCR (`ocrmypdf` + `tesseract`) for scanned documents, and Claude's own vision/reading capabilities for content extraction. Spreadsheets bypass the PDF route and are read directly with `openpyxl`.

The output is a clean `.md` file with YAML frontmatter, proper heading hierarchy, Mermaid diagrams where applicable, and no processing artifacts.

---

## Skill: `install`

### Purpose
Installs the `catalog.json` copy, then runs `check`.

### Invocation
```
/p4cc-converter:install
```

### Non-Goals
- Does not install tools automatically

---

## Skill: `check`

### Purpose
Read-only verification of qpdf, python3, libreoffice (version constraints), `openpyxl` (⚠️ when missing — only needed for spreadsheets), the optional OCR tools (ocrmypdf, tesseract + languages, pdftotext — ⚠️ when missing) and the shipped consolidation script. Prints a status table and install instructions for anything missing.

### Invocation
```
/p4cc-converter:check
```

### Non-Goals
- Does not install tools automatically
- `check` never modifies anything

---

## Skill: `any-to-md`

### Purpose

Converts one or more documents (PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, XLSM) to Markdown using a pipeline (6 conceptual steps plus an optional OCR step):

1. **Inventory** — resolve input glob, detect already-converted files, confirm with user
2. **To PDF** — convert non-PDF files via LibreOffice headless (permanent artifact)
2b. **OCR (optional)** — `ocrmypdf` adds a text layer to scanned/image-only pages → `<name>.ocr.pdf` (permanent artifact)
3. **Split** — divide PDF into 5-page chunks via qpdf (`.tmp.pdf`)
4. **Extract** — LLM reads each chunk sequentially and produces `.tmp.md`
5. **Consolidate** — Python script merges chunks into final `.md` with frontmatter
6. **Review** — LLM quality pass + cleanup of all `.tmp.*` files

### Invocation

```
/p4cc-converter:any-to-md [path/to/file-or-folder-or-glob] [--ocr auto|always|never]
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_ALL_TO_MD_PATTERN` | — | Input path/glob (overrides interactive prompt) |
| `AGENT_ALL_TO_MD_OUTPUT` | — | Output folder for `.md` files; empty or `"source"` = co-located with source |
| `AGENT_ALL_TO_MD_REPROCESS` | `false` | Set to `true` to reprocess already-converted files without prompting |
| `AGENT_ALL_TO_MD_OCR` | `auto` | OCR mode: `auto` (only documents with at least one page without text layer, detected with `pdftotext`; skipped with a warning if OCR tools are missing), `always` (`ocrmypdf --force-ocr`), `never` |
| `AGENT_ALL_TO_MD_OCR_LANG` | `spa+eng` | Tesseract language(s), `+`-separated |
| `AGENT_ALL_TO_MD_XLSX_MAX_ROWS` | `1000` | Max data rows per spreadsheet sheet; `0` = no limit |

### OCR behaviour

- `auto` runs `ocrmypdf --skip-text`, so pages that already have text are left untouched.
- The OCR text layer is a reading aid: Claude cross-checks numbers, codes and table cells against the page image, restores reading order from the layout and writes `[illegible]` instead of guessing.
- Chunks are always named after the source (`<name>_NNN-NNN.tmp.pdf`), never `<name>.ocr`, because the consolidation script locates chunks by that prefix.

### Format detection (Step 3)

The skill never trusts the file extension. `detect-format.py` (standard library only) reads the content of every candidate and returns its real format:

| Signature / structure | Detected |
|-----------------------|----------|
| `%PDF-` | `pdf` |
| ZIP with `word/` / `xl/` (+ `vbaProject.bin` → macro) / `ppt/` | `docx` / `xlsx` / `xlsm` / `pptx` |
| ZIP with `xl/workbook.bin`, or `mimetype` of OpenDocument | `xlsb`, `ods` / `odt` / `odp` (not supported) |
| OLE2 container with `WordDocument` / `PowerPoint Document` / `Workbook`/`Book` stream | `doc` / `ppt` / `xls` |
| Text: HTML, RTF, XML, CSV/TSV, plain, empty | not supported (skipped with an explanation) |

- Folder scans pre-filter by extension for speed; a file with a wrong or missing extension is converted when passed explicitly (single file, glob or list).
- Files whose extension does not match their real format are flagged in the inventory and processed from a **copy with the right extension in a temporary folder** (`.<name>.detected.tmp`), so generated files can never overwrite the user's file. `source:` in the frontmatter keeps the name the user provided; `source_format:` records the real format.

### Spreadsheets (Step 4c)

XLS/XLSX/XLSM skip PDF, OCR, split and chunk extraction:

1. `.xls` → `.xlsx` through LibreOffice into a temporary folder (`.<name>.xls2xlsx.tmp`, removed afterwards).
2. `xlsx-to-md.py` (openpyxl) writes one `## <sheet>` section per visible sheet, first row of the used range as table header. Hidden sheets are skipped and listed in the frontmatter (`hidden_sheets`); merged cells are written once; dates are ISO; `|` and newlines are escaped.
3. Values are the ones Excel stored. If formulas have no cached value, the skill recalculates the workbook through LibreOffice and retries; `--formulas` writes the formulas instead.
4. Sheets above `AGENT_ALL_TO_MD_XLSX_MAX_ROWS` (default 1000 data rows) are truncated with a note giving the total.
5. Review (Step 8) is limited to typos and table alignment — data is never altered.

Charts, images and pivot tables are not extracted.

### Output format

```yaml
---
source: manual.docx
source_format: docx
converted_via_pdf: true
converted: 2026-06-05T10:30:00
pages: 12
chunks: 3
chunk_size: 5
split_tool: qpdf
ocr: false
---

When OCR was applied: `ocr: true`, `ocr_tool: ocrmypdf`, `ocr_lang: <lang>`.
```

### Non-Goals

- Does not convert Markdown to other formats.
- Does not upload documents anywhere.
- Does not process images as standalone files (images embedded in documents are extracted/described inline). Standalone image inputs (PNG/JPG/TIFF) are out of scope.
- Does not install OCR tools automatically.

---

## External dependencies

| Tool | Required version | Use | Optional? |
|------|-----------------|-----|-----------|
| `qpdf` | `>=10.0.0` | PDF splitting | No |
| `python3` | `>=3.8.0` | Consolidation script | No |
| `libreoffice` | `>=7.0.0` | DOC/DOCX/PPT/PPTX → PDF, XLS → XLSX | Only if non-PDF inputs |
| `openpyxl` (Python package) | any | Read XLSX/XLSM | Only for spreadsheet inputs |
| `ocrmypdf` | any | OCR of scanned / image-only pages | Yes (`OCR_MODE=auto` degrades gracefully) |
| `tesseract` | any (+ language packs) | OCR engine used by `ocrmypdf` | Yes |
| `pdftotext` | any (poppler-utils) | Detect pages without text layer | Yes |

> `openpyxl` and the optional OCR tools are intentionally **not** listed in `catalog.json` `dependencies` (the schema has no optional flag); `check` verifies them separately and reports ⚠️.

---

## Changelog

| Version | Changes |
|---------|---------|
| 1.0.10 | `any-to-md` detects the real format by content (`detect-format.py`): handles wrong/missing extensions, skips unsupported content with an explanation; scripts record `source` and real `source_format`; `check` verifies the new script |
| 1.0.9 | Add spreadsheet support (XLS/XLSX/XLSM): Step 4c, `xlsx-to-md.py` (openpyxl), `AGENT_ALL_TO_MD_XLSX_MAX_ROWS`; `check` verifies openpyxl |
| 1.0.8 | Add optional OCR (`ocrmypdf`/`tesseract`): Step 4b, `--ocr` flag and `AGENT_ALL_TO_MD_OCR[_LANG]`; consolidation script records `ocr`, `ocr_tool`, `ocr_lang` in frontmatter and tolerates missing qpdf; `check` verifies OCR tools |
| 1.0.7 | Add `check` skill; `install` now creates folders/files and delegates verification to `check` |
| 1.0.4 | Fix qpdf constraint to >=10.0.0; fix SOURCE_FOLDER / OUTPUT_PATH variable consistency; clarify inventory loop and Step 6.1 tool; document AGENT_ALL_TO_MD_OUTPUT env var |
| 1.0.3 | Add input-path, glob/file selection and output-path parameters to any-to-md |
| 1.0.2 | Add `any-to-md` skill — full 6-step conversion pipeline |
| 1.0.1 | Add `setup` skill — dependency verification |
| 1.0.0 | Initial plugin scaffold |
