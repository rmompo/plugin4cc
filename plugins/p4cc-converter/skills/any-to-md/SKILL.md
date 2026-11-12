---
name: any-to-md
description: Converts PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX and XLSM documents to structured Markdown, detecting each file's real format from its content (not its extension). Text documents go through a 9-step pipeline (inventory → LibreOffice → optional OCR → qpdf split → LLM extraction → Python consolidation → LLM review, scanned pages OCR'd automatically); spreadsheets are read directly with openpyxl, one table per sheet. Also invoked explicitly as /p4cc-converter:any-to-md.
version: 10
argument-hint: "[path/to/file-or-folder-or-glob] [--ocr auto|always|never]"
allowed-tools: [Bash, Read, Write, AskUserQuestion]
---

# Any to Markdown

Converts documents (PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, XLSM) to structured, LLM-optimized Markdown. Text documents use a 9-step pipeline covering 7 conceptual phases: inventory → to-pdf → OCR (optional) → split → extract → consolidate → review. **The skill detects each file's real format itself, by content** (Step 3) — the extension is never trusted, so a `.docx` named `.pdf`, an `.xlsx` named `.xls` or an extensionless PDF are routed correctly. **Spreadsheets (XLS/XLSX/XLSM) skip the PDF route** — Step 4c reads them directly with `openpyxl` (one table per sheet) and they continue at Step 8.

```
CONSOLIDATE_SCRIPT = <plugin-cache>/resources/scripts/all-to-md-consolidate.py
XLSX_SCRIPT        = <plugin-cache>/resources/scripts/xlsx-to-md.py
DETECT_SCRIPT      = <plugin-cache>/resources/scripts/detect-format.py
```

Where `<plugin-cache>` = `~/.claude/plugins/cache/plugin4cc/p4cc-converter/<version>/`

**Prerequisites:** run `/p4cc-converter:install` first to verify tool availability.

**Processing model:** for each document in the inventory, run its route in full before moving to the next — text documents: Steps 4 through 9; spreadsheets: Steps 4c, 8 and 9. Steps 4 and 5 reference "each file" within that per-document loop — not a batch over the whole inventory.

**Key variables** (established in Step 1, used throughout):

| Variable | Value |
|----------|-------|
| `ORIG_FOLDER` | Absolute path to the folder containing the file the user provided |
| `SOURCE_FOLDER` | Folder where the document's intermediate files live. Equals `ORIG_FOLDER`, except for files whose extension does not match their real format: then it is the temporary `WORK_DIR` (Step 3) |
| `FORMAT` | Real format detected from the file content (Step 3): `pdf`, `doc`, `docx`, `ppt`, `pptx`, `xls`, `xlsx` or `xlsm` |
| `WORK_DIR` | `{ORIG_FOLDER}/.{name}.detected.tmp` — only for mismatched files; deleted at the end of the document's route |
| `OUTPUT_PATH` | Destination folder for `.md` files; `null` means co-located with source |
| `reprocess` | Boolean — whether to reprocess already-converted files |
| `OCR_MODE` | `auto` (default), `always` or `never` — see Step 1.5 |
| `OCR_LANG` | Tesseract language(s), `+`-separated (default `spa+eng`) |

---

## Step 1 — Resolve plugin cache and collect parameters

```bash
PLUGIN_CACHE=$(ls -d ~/.claude/plugins/cache/plugin4cc/p4cc-converter/*/ 2>/dev/null | sort -V | tail -1)
CONSOLIDATE_SCRIPT="$PLUGIN_CACHE/resources/scripts/all-to-md-consolidate.py"
XLSX_SCRIPT="$PLUGIN_CACHE/resources/scripts/xlsx-to-md.py"
DETECT_SCRIPT="$PLUGIN_CACHE/resources/scripts/detect-format.py"
```

Use **AskUserQuestion** to collect the three conversion parameters (or resolve from environment / skill argument):

### 1.1 — Input path

Resolve in order of precedence:
1. Environment variable `AGENT_ALL_TO_MD_PATTERN`
2. Argument passed to the skill invocation
3. Ask the user:

```
Input path — where are the source documents?
You can specify:
  - A folder:      /home/user/docs/
  - A single file: /home/user/docs/manual.docx
  - A glob:        /home/user/docs/reports/*.pdf

Supported formats: .pdf  .doc  .docx  .ppt  .pptx  .xls  .xlsx  .xlsm
(The real format is detected from each file's content — the extension does not decide.)
```

Expand `~` to the actual home directory before any file operation.

### 1.2 — Selection within the input path

If the input path is a **folder**, ask the user how to select files within it:
- **All supported files** — process every `.pdf`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx`, `.xlsm` found (recursive if needed). Folder scans pre-filter by extension for speed; to convert a file with a wrong or missing extension, pass it explicitly (single file, glob or file list)
- **Glob pattern** — user provides a pattern relative to the input path (e.g. `reports_2026_*.pdf`)
- **Explicit file(s)** — user lists specific filenames

If the input path is already a **single file** or a **full glob** → skip this sub-question and use it directly.

### 1.3 — Output path

Resolve in order of precedence:
1. **Environment variable `AGENT_ALL_TO_MD_OUTPUT`**:
   - If unset, empty, or equal to `"source"` → `OUTPUT_PATH = null` (co-located mode)
   - Otherwise → `OUTPUT_PATH = <value>` (must be an absolute path; validate it exists or offer to create it)
2. **AskUserQuestion** (only if env var is unset or empty):
   - **Same folder as source** *(Recommended)* — each `.md` is saved next to its source file → `OUTPUT_PATH = null`
   - **Custom path** — user provides an absolute path to a different destination folder → validate it exists (or offer to create it); set `OUTPUT_PATH`

### 1.4 — Reprocess flag

- If `AGENT_ALL_TO_MD_REPROCESS=true` → `reprocess = true` (forced by env var; Step 3 will NOT ask again)
- Otherwise → `reprocess = false` (default; Step 3 may ask interactively if already-converted files are found)

### 1.5 — OCR mode

OCR makes scanned or image-only pages readable. It is **optional**: it needs `ocrmypdf` (which uses `tesseract`) and, for `auto` detection, `pdftotext`.

Resolve `OCR_MODE` in order of precedence:
1. Environment variable `AGENT_ALL_TO_MD_OCR`
2. Flag `--ocr <mode>` passed to the skill invocation
3. Default: `auto` (never prompts)

| Mode | Behaviour |
|------|-----------|
| `auto` | Run OCR only on documents where at least one page has no text layer (detected in Step 4b). Silently skipped if OCR tools are missing — a warning is shown in the inventory |
| `always` | Force OCR on every PDF, discarding any existing text layer (`--force-ocr`) |
| `never` | Never run OCR — the pipeline behaves exactly as before |

Resolve `OCR_LANG`: environment variable `AGENT_ALL_TO_MD_OCR_LANG`, otherwise `spa+eng`.

### 1.6 — Spreadsheet row limit

Only used for spreadsheets. `XLSX_MAX_ROWS`: environment variable `AGENT_ALL_TO_MD_XLSX_MAX_ROWS`, otherwise `1000` data rows per sheet (`0` = no limit). Larger sheets are truncated with a note stating the total, because huge tables are rarely useful as LLM context. Never ask interactively.

---

## Step 2 — Verify tools

Before building the inventory, verify the three required tools are present:

```bash
which qpdf    && qpdf --version 2>&1 | head -1
which python3 && python3 --version 2>&1 | head -1
which libreoffice && libreoffice --version 2>&1 | head -1
```

- `libreoffice` is **mandatory** only if the inventory will contain DOC/DOCX/PPT/PPTX/XLS files.
- If any required tool is missing → stop and direct the user to run `/p4cc-converter:check`.

If the inventory will contain XLS/XLSX/XLSM files (by their **real** format — re-check this item after Step 3 once formats are detected), also verify the Python package `openpyxl`:

```bash
python3 -c "import openpyxl; print(openpyxl.__version__)"
```

If missing → **stop** and show: `sudo apt install python3-openpyxl` (or `pip install openpyxl`) and direct the user to `/p4cc-converter:check`.

If `OCR_MODE` ≠ `never`, also check the **optional** OCR tools:

```bash
which ocrmypdf  && ocrmypdf --version 2>&1 | head -1
which tesseract && tesseract --list-langs 2>&1      # every language in OCR_LANG must be listed
which pdftotext && pdftotext -v 2>&1 | head -1      # needed only for auto detection
```

| Situation | Action |
|-----------|--------|
| `OCR_MODE=always` and `ocrmypdf` / `tesseract` missing | **Stop** — direct the user to `/p4cc-converter:check` for install instructions |
| `OCR_MODE=auto` and `ocrmypdf` / `tesseract` / `pdftotext` missing | Continue with `OCR_EFFECTIVE=off` and warn: `OCR tools not found — scanned pages will rely on vision only (run /p4cc-converter:check)` |
| A language in `OCR_LANG` is not installed | Stop (`always`) or warn and continue without OCR (`auto`); show `sudo apt install tesseract-ocr-<lang>` |

---

## Step 3 — Build inventory

Resolve the glob pattern and collect files with extensions: `.pdf`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx`, `.xlsm`. Ignore Office lock/temp files (`~$*`) and hidden `.*.tmp` work folders.

### 3.1 — Detect the real format (by content)

Run the detector once over every candidate file:

```bash
python3 "$DETECT_SCRIPT" file1 file2 ...     # prints a JSON array, one object per file
```

Each object has `detected` (real format), `ext` (extension of the name), `mismatch`, `supported`, `route` (`pdf` | `office-to-pdf` | `spreadsheet` | `null`) and `note`. **Use `detected`, never the extension, to choose the route.** Files with a recognised format keep working exactly as before:

| `detected` | Route |
|------------|-------|
| `pdf` | `pdf` |
| `doc`, `docx`, `ppt`, `pptx` | `office-to-pdf` |
| `xls`, `xlsx`, `xlsm` | `spreadsheet` |
| anything else (`html`, `rtf`, `csv`, `xml`, `ods`/`odt`/`odp`, `xlsb`, `text`, `empty`, `unknown`, `unreadable`) | not supported → **skipped**, with the detector's `note` explaining how to proceed (e.g. an `.xls` that is really HTML exported from a web app: open it and save as `.xlsx`) |

Set `FORMAT = detected` for each supported file.

### 3.2 — Files whose extension is wrong

If `mismatch = true` and the format is supported (e.g. `report.pdf` that is really a DOCX, `export.xls` that is really an XLSX, or a file with no extension):

1. Warn in the inventory: `⚠ report.pdf is really a DOCX — detected by content, extension ignored`.
2. Work on a **copy with the correct extension, in a temporary folder** — never next to the original, so that generated files (`{name}.pdf`, `.ocr.pdf`) can never overwrite the user's file:

```bash
WORK_DIR="{ORIG_FOLDER}/.{name}.detected.tmp"
mkdir -p "$WORK_DIR" && cp "{ORIG_FOLDER}/{orig-filename}" "$WORK_DIR/{name}.{FORMAT}"
```

3. For the whole route of that document `SOURCE_FOLDER = WORK_DIR`. The final `.md` still goes to `OUTPUT_PATH`, or to `ORIG_FOLDER` when co-located. Remove `WORK_DIR` at the end of the route (Step 8.5 / 4c.4).

If `mismatch = false`: `SOURCE_FOLDER = ORIG_FOLDER`, no copy, nothing changes.

> `{name}` is the original file name without its extension; `{orig-filename}` is the full name as the user provided it. In every later step `{ext}` means `FORMAT`.

### 3.3 — Conversion route

| Detected format | Conversion route |
|-----------------|-----------------|
| `FORMAT` = `pdf` | Direct → Step 4b (OCR, if needed) → Step 5 (split) |
| `FORMAT` = `doc`, `docx`, `ppt`, `pptx` | Step 4 (to PDF) → Step 4b (OCR, if needed) → Step 5 (split) |
| `FORMAT` = `xls`, `xlsx`, `xlsm` | Step 4c (openpyxl, direct — no PDF, no OCR, no split) → Step 8 (review) |

- Compute the target `.md` path:
  - If `OUTPUT_PATH` is set → `{OUTPUT_PATH}/{name}.md`
  - If `OUTPUT_PATH` is null → `{ORIG_FOLDER}/{name}.md` (co-located with the original file)
- If the target `.md` already exists AND `reprocess = false` → mark as **skipped**.
- If the target `.md` already exists AND `reprocess = true` → include in inventory.
- If the target `.md` does not exist → include in inventory.

Sort the inventory alphabetically by path.

**If there are skipped files AND `reprocess = false` (not forced by env var in Step 1.4)**, ask the user:
```
N file(s) already converted (their .md exists):
  - input/docs/manual.docx → output/manual.md (exists)

Do you want to reprocess them?
  1 - Yes, reprocess all
  2 - No, skip them (continue with pending only)
```

If `reprocess = true` (set by env var in Step 1.4) → include all files without asking.

**Print final inventory summary** and ask for confirmation before proceeding:
```
══════════════════════════════════════════
  DOCUMENT INVENTORY
══════════════════════════════════════════
  Files to convert:  N
  Files skipped:     N
  Input path:        [input path]
  Output path:       [output path or "co-located with source"]
  Reprocess:         yes/no
  OCR:               auto|always|never  (lang: spa+eng)  [tools missing → off]
══════════════════════════════════════════

Files to process:
  1. input/docs/manual.docx       [docx → pdf → md]
  2. input/docs/guide.pdf         [pdf → md]
  3. input/docs/slides.pptx       [pptx → pdf → md]
  4. input/docs/budget.xlsx       [xlsx → md]
  5. input/docs/report.pdf        [docx → pdf → md]  ⚠ extension says PDF, content is DOCX

Skipped (not supported):
  - input/docs/export.xls         html — open it and save as .xlsx

Proceed with conversion? [y/N]
```

If the inventory is empty → stop with a clear message.

---

## Step 4 — Convert non-PDF files to PDF (LibreOffice)

Process only DOC/DOCX/PPT/PPTX files from the inventory.

For each file, check if `{name}.pdf` already exists in the same folder:
- **Exists** → skip conversion, reuse the existing PDF. Notify: `→ manual.docx: PDF already exists (manual.pdf), reusing`
- **Not exists** → convert:

```bash
libreoffice --headless --convert-to pdf --outdir {SOURCE_FOLDER} {SOURCE_FOLDER}/{name}.{FORMAT}
```

The generated PDF keeps the same filename, only the extension changes. It is a **permanent artifact** — never deleted.

After each conversion, verify:
- `{name}.pdf` exists in the correct folder
- Size is greater than 0 bytes

If verification fails → stop and report which file failed.

**Summary:**
```
══════════════════════════════════════════
  PDF CONVERSION SUMMARY
══════════════════════════════════════════
  Converted:   2
    ✓ manual.docx   → manual.pdf  (new)
    → slides.pptx   → slides.pdf  (already existed, reused)
  Native PDF:  1
    → guide.pdf  (no conversion needed)
══════════════════════════════════════════
```

---

## Step 4b — OCR (optional)

Skip this step entirely when `OCR_MODE=never` or `OCR_EFFECTIVE=off`.

Let `PDF_BASE` = `{SOURCE_FOLDER}/{name}.pdf` (the native PDF, or the one generated in Step 4) and `PDF_FOR_SPLIT` = the file Step 5 will split. Default: `PDF_FOR_SPLIT = PDF_BASE`, `ocr_applied = false`.

### 4b.1 — Decide

- `OCR_MODE=always` → OCR is needed.
- `OCR_MODE=auto` → detect pages without a text layer:

```bash
pdftotext "$PDF_BASE" - 2>/dev/null | python3 -c "
import sys
pages = sys.stdin.read().split('\f')
if pages and not pages[-1].strip(): pages.pop()
empty = [i+1 for i,p in enumerate(pages) if len(''.join(p.split())) < 20]
print(len(empty), len(pages), *empty[:20])
"
```

  If at least one page has fewer than 20 non-whitespace characters → OCR is needed. Report which pages: `→ guide.pdf: 8 of 12 pages have no text layer — OCR needed`.

If OCR is not needed → keep defaults and continue to Step 5.

### 4b.2 — Run OCR

If `{SOURCE_FOLDER}/{name}.ocr.pdf` already exists and `reprocess = false` → reuse it. Otherwise:

```bash
# auto  — OCR only pages that have no text layer
ocrmypdf --skip-text --language "$OCR_LANG" --output-type pdf \
  "{SOURCE_FOLDER}/{name}.pdf" "{SOURCE_FOLDER}/{name}.ocr.pdf"

# always — rasterize and OCR every page (existing text layer is discarded)
ocrmypdf --force-ocr --language "$OCR_LANG" --output-type pdf \
  "{SOURCE_FOLDER}/{name}.pdf" "{SOURCE_FOLDER}/{name}.ocr.pdf"
```

Verify `{name}.ocr.pdf` exists and is larger than 0 bytes, then set `PDF_FOR_SPLIT = {name}.ocr.pdf` and `ocr_applied = true`.

If `ocrmypdf` fails (encrypted or corrupt PDF, etc.) → in `auto` mode warn and continue with the original PDF (`ocr_applied = false`); in `always` mode stop and report the error.

`{name}.ocr.pdf` is a **permanent artifact** (OCR is slow, so it is reused on reprocessing) — never deleted in Step 8.5. The source file and `{name}.pdf` are never modified.

**Summary:**
```
══════════════════════════════════════════
  OCR SUMMARY
══════════════════════════════════════════
  guide.pdf    → guide.ocr.pdf   (8/12 pages OCR'd, lang: spa+eng)
  manual.pdf   → no OCR needed   (text layer present)
══════════════════════════════════════════
```

---

## Step 4c — Convert spreadsheets (openpyxl)

Process only XLS/XLSX/XLSM files from the inventory. These **skip Steps 4, 4b, 5, 6 and 7**: tables are read directly from the workbook (a PDF would cut them across pages).

### 4c.1 — Legacy `.xls` → `.xlsx`

`openpyxl` cannot read `.xls`. Convert it with LibreOffice into a **temporary** folder (never next to the source, so it cannot collide with an existing `{name}.xlsx`):

```bash
TMP_X="{SOURCE_FOLDER}/.{name}.xls2xlsx.tmp"
mkdir -p "$TMP_X"
libreoffice --headless --convert-to xlsx --outdir "$TMP_X" "{SOURCE_FOLDER}/{name}.xls"
```

`XLSX_INPUT = $TMP_X/{name}.xlsx`. For `.xlsx` / `.xlsm`, `XLSX_INPUT` is the source file itself. Verify the converted file exists and is larger than 0 bytes.

### 4c.2 — Convert

```bash
python3 "$XLSX_SCRIPT" \
  --source   "$XLSX_INPUT" \
  --original "{ORIG_FOLDER}/{orig-filename}" \
  --source-format "$FORMAT" \
  --output   "{output-path}/{name}.md" \
  --max-rows "$XLSX_MAX_ROWS"
```

Where `{output-path}` is `$OUTPUT_PATH` if set, otherwise `{ORIG_FOLDER}`. `--original` and `--source-format` make the frontmatter name the file the user provided (`source:`) and its **real** format (`source_format:`), which matters for `.xls` and for mismatched files.

The script writes one `## <sheet>` section per **visible** sheet (hidden sheets are listed in the frontmatter as `hidden_sheets`), with the first row of the used range as table header, merged cells written once, dates in ISO format, and `|` / newlines escaped. Charts, images and pivot tables are **not** extracted (the script reports how many it skipped).

### 4c.3 — Formulas without cached values

By default the script writes the values Excel stored in the file. If it warns `N celdas con fórmula sin valor calculado` (workbook generated by a library and never opened in Excel), recalculate it through LibreOffice and re-run Step 4c.2 on the result:

```bash
TMP_X="{SOURCE_FOLDER}/.{name}.recalc.tmp"; mkdir -p "$TMP_X"
libreoffice --headless --convert-to xlsx --outdir "$TMP_X" "{SOURCE_FOLDER}/{name}.{FORMAT}"
# XLSX_INPUT = $TMP_X/{name}.xlsx
```

If the user explicitly wants formulas instead of results, add `--formulas`.

### 4c.4 — Verify and clean up

Verify `{name}.md` exists and is not empty, then remove the temporary folder(s) (`.{name}.xls2xlsx.tmp`, `.{name}.recalc.tmp`, and `WORK_DIR` if it was created in Step 3.2) with `rm -r`. Continue at Step 8 (review) — **for spreadsheets, only 8.1 (typos in headers/text) and 8.3 (table alignment) apply; never rewrite, merge or drop data rows or cells.**

---

## Step 5 — Split PDF into chunks (qpdf)

For each document in the inventory, determine the PDF to split (`PDF_FOR_SPLIT`):

| Source file | PDF for qpdf |
|-------------|-------------|
| `guide.pdf` | `guide.pdf`, or `guide.ocr.pdf` if OCR was applied (Step 4b) |
| `manual.docx` | `manual.pdf` (generated in Step 4), or `manual.ocr.pdf` if OCR was applied |
| `slides.pptx` | `slides.pdf` (generated in Step 4), or `slides.ocr.pdf` if OCR was applied |

**Chunk names always use `{name}` (the source name), never `{name}.ocr`** — the consolidation script locates chunks by that prefix.

**Get page count:**
```bash
qpdf --show-npages {PDF_FOR_SPLIT}
```

**Calculate chunks** (chunk size = 5 pages):
```
chunk 1: pages 1  →  5   → {name}_001-005.tmp.pdf
chunk 2: pages 6  → 10   → {name}_006-010.tmp.pdf
...
chunk k: pages X  →  N   → {name}_0XX-0YY.tmp.pdf
```

Numeric format: 3 digits zero-padded (`001`, `006`, `011`…). **Note:** this naming supports documents up to 999 pages. Documents with ≥1000 pages would require 4-digit padding — flag this case to the user and stop.

**Generate each chunk:**
```bash
qpdf {PDF_FOR_SPLIT} --pages . {page_start}-{page_end} -- {SOURCE_FOLDER}/{name}_{start_fmt}-{end_fmt}.tmp.pdf
```

Verify all expected chunks were created and have size > 0.

**Summary:**
```
══════════════════════════════════════════
  SPLIT SUMMARY
══════════════════════════════════════════
  File:    manual.docx (via manual.pdf)
  Pages:   12
  Chunks:  3
    → manual_001-005.tmp.pdf  (pp. 1-5)
    → manual_006-010.tmp.pdf  (pp. 6-10)
    → manual_011-012.tmp.pdf  (pp. 11-12)
══════════════════════════════════════════
```

---

## Step 6 — Extract content (LLM reads each chunk)

Process chunks **strictly sequentially** — one at a time, in ascending page order. Do not start the next chunk until the previous one is complete.

For each chunk `.tmp.pdf`:

### 6.1 Read the chunk PDF

Use the **Read tool** to open the chunk `.tmp.pdf` — the model interprets text and images directly from the file. Do not use external text extractors (pdftotext, pdfimages, etc.) for this step: when OCR was applied, its result is already embedded in the chunk as a text layer.

**If `ocr_applied = true`:** the chunk carries an OCR text layer for pages that had none. Treat it as a reading aid, not as ground truth — the visual content of the page decides:
- Use the text layer for running text; it is cheaper and avoids transcription slips.
- Cross-check numbers, identifiers, codes, names and table cells against what is visible on the page; correct OCR errors (`0`/`O`, `1`/`l`, broken words, split columns).
- Restore reading order and structure (headings, tables, lists) from the visual layout — OCR often scrambles multi-column pages.
- If a passage is illegible even visually, write `[illegible]` instead of guessing.

### 6.2 Apply omission rules

**OMIT the following elements:**

| Element | Detection criterion |
|---------|---------------------|
| Page headers | Text repeated at the top of multiple pages |
| Page footers | Text repeated at the bottom of multiple pages |
| Page numbers | Isolated number in header or footer |
| TOC / Index | Always — regardless of position in the document |
| Document control sheet | Metadata table (title, version, date, authors) |
| Change history table | Document version history |

### 6.3 Text extraction rules

| Element | Markdown conversion |
|---------|---------------------|
| Main title | `# Title` |
| Sections | `## Section` / `### Subsection` |
| Paragraphs | Plain text |
| Numbered lists | `1. Item` |
| Bullet lists | `- Item` |
| Tables | Standard Markdown tables |
| Source code | ` ```language ` block with syntax highlighting |
| Shell / terminal commands | ` ```bash ` block |
| Notes / warnings / notices | `> **Note:** text` |
| Internal cross-references | `[text](#section-anchor)` |
| External URLs | `[text](url)` |
| Slides (PPT/PPTX origin) | Each slide as `##` section, slide title as heading |

### 6.4 Image interpretation rules (priority order)

| Priority | Image type | Conversion |
|----------|------------|------------|
| 1 | Flow / process diagram | Mermaid `flowchart` |
| 2 | Sequence diagram | Mermaid `sequenceDiagram` |
| 3 | Class / entity diagram | Mermaid `classDiagram` / `erDiagram` |
| 4 | State diagram | Mermaid `stateDiagram-v2` |
| 5 | System / infrastructure architecture | Mermaid `graph` |
| 6 | UI / mockup / screenshot | Textual description of layout (inputs, buttons, panels, labels, arrangement) |
| 7 | OCR image — code / shell / config | Code block with detected language |
| 8 | OCR image — general text | Plain extracted text |
| 9 | General image (photo, illustration) | Narrative description: subject, context, colors, action |
| 10 | Uninterpretable image | `[Image: {description or available alt text}]` |

### 6.5 Write the .tmp.md

The `.tmp.md` file has **NO frontmatter**. It starts directly with the extracted content.

Save to: `{SOURCE_FOLDER}/{name}_{page_start}-{page_end}.tmp.md`

**Summary after all chunks of a file:**
```
══════════════════════════════════════════
  EXTRACTION COMPLETE
══════════════════════════════════════════
  File:    manual.docx
  Chunks:  3
    ✓ manual_001-005.tmp.md
    ✓ manual_006-010.tmp.md
    ✓ manual_011-012.tmp.md
══════════════════════════════════════════
```

---

## Step 7 — Consolidate chunks (Python script)

Before consolidating, verify that all expected `.tmp.md` files exist (one per `.tmp.pdf` chunk from Step 5). If any is missing → stop and report.

Run the consolidation script:

```bash
python3 "$CONSOLIDATE_SCRIPT" \
  --source {SOURCE_FOLDER}/{name}.{FORMAT} \
  --pdf    {SOURCE_FOLDER}/{name}.pdf \
  --output {output-path}/{name}.md \
  [--ocr --ocr-lang "$OCR_LANG"] [--original-name "{orig-filename}"]
```

Add `--ocr --ocr-lang "$OCR_LANG"` only when `ocr_applied = true`, and `--original-name` only for mismatched files (so `source:` names the file the user provided while `source_format:` stays the real format). `--pdf` always points to `{name}.pdf` (never `{name}.ocr.pdf`).

Where `{output-path}` is:
- `$OUTPUT_PATH` if set (Step 1.3)
- `{ORIG_FOLDER}` if `OUTPUT_PATH` is null (co-located mode)

Parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--source` | Source file with its real extension (for metadata) | `input/docs/manual.docx` |
| `--original-name` | Optional — name the user provided, when it differs from `--source` | `report.pdf` |
| `--pdf` | Reference PDF (for page count) | `input/docs/manual.pdf` |
| `--output` | Final Markdown output path | `output/manual.md` |
| `--ocr` | Optional flag — records `ocr: true` in the frontmatter | |
| `--ocr-lang` | Optional — OCR language(s) recorded in the frontmatter | `spa+eng` |

The script automatically:
1. Locates all `.tmp.md` for the document (same prefix, same folder, ascending order)
2. Strips intermediate chunk frontmatter
3. Removes redundant chunk-boundary headers
4. Unifies section hierarchy
5. Generates consolidated frontmatter
6. Writes the final `{name}.md`

**Generated frontmatter:**
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
```

When `--ocr` is passed the script writes `ocr: true`, `ocr_tool: ocrmypdf` and `ocr_lang: <lang>` instead of `ocr: false`.

Verify that `{name}.md` has been created and is not empty.

---

## Step 8 — Review and cleanup

Read the complete `{name}.md` **before making any modifications** — full context is required.

### 8.1 Spelling and grammar

> Spreadsheets (Step 4c): see the note at the end of Step 4c — only 8.1 and 8.3 apply, and data is never altered.

- Correct spelling and grammar errors.
- Keep technical terms in their original language (do not translate class names, methods, commands, paths).

### 8.2 Clarity and synthesis

| Aspect | Criterion |
|--------|-----------|
| Redundancies | Remove if the same information appears in multiple sections without adding context |
| Complex sentences | Simplify without losing technical precision |
| Empty sections | Remove or merge sections without relevant content |

### 8.3 LLM optimization

| Aspect | Criterion |
|--------|-----------|
| Code blocks | Verify all have a language specifier |
| Mermaid diagrams | Verify correct syntax |
| Tables | Verify correct column and header alignment |
| Heading hierarchy | `#` → `##` → `###` without skipping levels |
| Ambiguities | Add minimal context to sections that may be cryptic out of document context |
| Terminology | Consistent use of the same terms throughout |

### 8.4 Narrative continuity

| Aspect | Criterion |
|--------|-----------|
| Logical flow | Sections follow a logical progression |
| Artificial phrases | Remove phrases generated by fragmented processing ("As mentioned earlier…", "In the next section…") |
| Terminological coherence | Same concept named the same way throughout |
| Example continuity | Examples spanning multiple chunks must be seamlessly integrated |

### 8.5 Cleanup of temporary files

> Spreadsheets have no chunk files — their temporary folders were already removed in Step 4c.4; skip this sub-step.

Once `{name}.md` is confirmed correct, remove all temporary files from **`SOURCE_FOLDER`** (the folder of the source document — NOT from `OUTPUT_PATH`, which only contains the final `.md`):

```bash
# Remove temporary PDF chunks — always in SOURCE_FOLDER
rm {SOURCE_FOLDER}/{name}_*.tmp.pdf

# Remove temporary Markdown chunks — always in SOURCE_FOLDER
rm {SOURCE_FOLDER}/{name}_*.tmp.md
```

**For mismatched files `SOURCE_FOLDER` is `WORK_DIR`, which is deleted entirely at this point (`rm -r "$WORK_DIR"`) — its `{name}.pdf` / `{name}.ocr.pdf` are not kept, and the user's original file is never modified.**

**For regular files, the `{SOURCE_FOLDER}/{name}.pdf` (PDF converted from DOC/DOCX/PPT/PPTX) and `{SOURCE_FOLDER}/{name}.ocr.pdf` (OCR output, Step 4b) are NOT deleted** — they are permanent artifacts reusable for future reprocessing.

Confirm deletion by listing the removed files.

---

## Step 9 — Final summary (per document)

```
══════════════════════════════════════════
  DOCUMENT CONVERTED SUCCESSFULLY
══════════════════════════════════════════
  Source:      {SOURCE_FOLDER}/manual.docx
  PDF:         {SOURCE_FOLDER}/manual.pdf  (preserved)
  Output:      {output-path}/manual.md
  Pages:       12
  Chunks:      3
  Temp files:  deleted (6 files)
══════════════════════════════════════════
```

For native PDF sources:
```
══════════════════════════════════════════
  DOCUMENT CONVERTED SUCCESSFULLY
══════════════════════════════════════════
  Source:      {SOURCE_FOLDER}/guide.pdf
  Output:      {output-path}/guide.md
  PDF (OCR):   {SOURCE_FOLDER}/guide.ocr.pdf  (preserved; omit this line if OCR was not applied)
  Pages:       7
  Chunks:      2
  Temp files:  deleted (4 files)
══════════════════════════════════════════
```

For spreadsheets:
```
══════════════════════════════════════════
  DOCUMENT CONVERTED SUCCESSFULLY
══════════════════════════════════════════
  Source:      {SOURCE_FOLDER}/budget.xlsx
  Output:      {output-path}/budget.md
  Sheets:      3 visible (1 hidden skipped)
  Rows:        Ventas 120 · Grande 1000 (350 omitted) · Resumen 12
  Temp files:  deleted
══════════════════════════════════════════
```

Where `{output-path}` = `OUTPUT_PATH` if set, or `ORIG_FOLDER` if null (co-located). For mismatched files add a line `Detected:    docx (extension said .pdf)` and omit the `PDF:` lines (the work folder was removed).

**If the inventory has more files**, repeat the document's route (Steps 4–9, or 4c → 8 → 9 for spreadsheets) for the next document in order.
