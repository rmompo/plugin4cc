# p4cc-converter

Document-to-Markdown converter plugin for Claude Code. Converts PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX and XLSM files to structured, LLM-optimized Markdown using a local pipeline with optional OCR for scanned documents.

## Pipeline

`any-to-md` detects every file's **real format from its content** (file signature and internal structure), never from the extension — a `.docx` named `.pdf`, an `.xlsx` named `.xls` or an extensionless PDF are routed correctly, and mismatches are flagged in the inventory. Unsupported content (HTML disguised as `.xls`, RTF, CSV, ODF, `.xlsb`…) is skipped with an explanation of how to proceed.

Text documents:

```
Input (PDF/DOC/DOCX/PPT/PPTX)
    ↓ LibreOffice (non-PDF only)
    PDF
    ↓ OCR (ocrmypdf — only scanned / image-only pages, optional)
    PDF with text layer
    ↓ qpdf (5-page chunks)
    .tmp.pdf chunks
    ↓ LLM extraction (sequential)
    .tmp.md chunks
    ↓ Python consolidation script
    .md (with frontmatter)
    ↓ LLM review + cleanup
    Final .md (LLM-optimized)
```

Spreadsheets (XLS / XLSX / XLSM) skip the PDF route:

```
.xls  → LibreOffice → .xlsx (temporary)
.xlsx / .xlsm
    ↓ openpyxl (xlsx-to-md.py): one "## sheet" section per visible sheet, one table each
    .md (with frontmatter)
    ↓ light LLM review (data is never altered)
    Final .md
```

## Skills

| Skill | Invocation | What it does |
|-------|-----------|--------------|
| `install` | `/p4cc-converter:install` | Installs the catalog copy, then runs `check`. |
| `check` | `/p4cc-converter:check` | Read-only check of qpdf, python3, libreoffice, openpyxl, optional OCR tools and the conversion and detection scripts. Reports how to fix anything missing. |
| `any-to-md` | `/p4cc-converter:any-to-md [path]` | Converts documents to structured Markdown (OCR for scanned pages, direct table extraction for spreadsheets) |

## Requirements

| Tool | Version | Purpose |
|------|---------|---------|
| `qpdf` | ≥11.0.0 | Split PDF into chunks |
| `python3` | ≥3.8.0 | Consolidation script |
| `libreoffice` | ≥7.0.0 | Convert DOC/DOCX/PPT/PPTX to PDF and XLS to XLSX |
| `openpyxl` *(only for spreadsheets)* | any | Read XLSX/XLSM (`sudo apt install python3-openpyxl`) |
| `ocrmypdf` + `tesseract` *(optional)* | any | OCR for scanned or image-only pages |
| `pdftotext` *(optional)* | any | Detect pages without a text layer (`auto` mode) |

## Quick start

```bash
# 1. Install and verify dependencies
/p4cc-converter:install
/p4cc-converter:check

# 2. Convert a document
/p4cc-converter:any-to-md input/docs/manual.docx

# 3. Convert a whole folder
/p4cc-converter:any-to-md input/docs/
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_ALL_TO_MD_PATTERN` | — | Input path/glob (overrides interactive prompt) |
| `AGENT_ALL_TO_MD_REPROCESS` | `false` | Set to `true` to reprocess already-converted files |
| `AGENT_ALL_TO_MD_OCR` | `auto` | `auto` = OCR only documents with pages lacking a text layer, `always` = force OCR, `never` = disable (also `--ocr <mode>`) |
| `AGENT_ALL_TO_MD_OCR_LANG` | `spa+eng` | Tesseract language(s), `+`-separated |
| `AGENT_ALL_TO_MD_XLSX_MAX_ROWS` | `1000` | Max data rows per spreadsheet sheet (`0` = no limit); extra rows are omitted with a note |

## OCR

Scanned or image-only pages are OCR'd with `ocrmypdf` before splitting. The result is saved as `<name>.ocr.pdf` (kept for reuse) and the model cross-checks the OCR text against the page image, so layout, tables and diagrams still come from vision. If the OCR tools are missing, `auto` mode continues without OCR and warns; run `/p4cc-converter:check` for install instructions.

## Spreadsheets

Each visible sheet becomes a `## <sheet>` section with a Markdown table (first row = header). Hidden sheets are skipped and listed in the frontmatter; merged cells are written once; dates are ISO; formulas are written as their calculated values (workbooks never calculated by Excel are recalculated through LibreOffice). Charts, images and pivot tables are not extracted.

## Output

Each converted document produces a `.md` file in the same folder as the source, with YAML frontmatter:

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
ocr: false        # true + ocr_tool / ocr_lang when OCR was applied
---
```

## Installation

```bash
claude plugins marketplace add rmompo/plugin4cc
claude plugins install p4cc-converter
```
