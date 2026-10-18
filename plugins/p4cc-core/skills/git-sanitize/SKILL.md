---
name: git-sanitize
description: Ensures the current git repo has correct line-ending hygiene. At session start, silently checks for .gitattributes with eol=lf and CRLF-contaminated tracked files. Reports and fixes issues. Also invoked explicitly as /p4cc-core:git-sanitize.
version: 1
trigger: session-start
allowed-tools: [Bash, Write, Edit, AskUserQuestion]
---

# git-sanitize

Ensures every git repo has `.gitattributes` enforcing LF line endings, `core.longpaths` enabled, converts any CRLF in tracked files to LF, keeps scripts executable, and enforces UTF-8 (BOM only for `*.ps1`).

**When triggered at session start**: silent if everything is clean; acts only when issues are found.  
**When invoked explicitly** (`/p4cc-core:git-sanitize`): always prints a full status report.

---

## Step 1 — Detect git repo

```bash
git rev-parse --show-toplevel 2>/dev/null
```

If the command fails (not a git repo): **exit silently**. No output.

Store the result as `REPO_ROOT`.

---

## Step 2 — Check .gitattributes

```bash
cat "$REPO_ROOT/.gitattributes" 2>/dev/null
```

The file is considered **compliant** if it contains a line matching:
```
* text=auto eol=lf
```
(leading whitespace and inline comments are ignored when checking).

### If missing or non-compliant

Create or update `$REPO_ROOT/.gitattributes`. If the file exists, prepend the rule at the top; if it does not exist, create it with this content:

```
# Force LF line endings for all text files, regardless of OS or core.autocrlf
* text=auto eol=lf

# Binary files — never touch line endings
*.png   binary
*.jpg   binary
*.jpeg  binary
*.gif   binary
*.ico   binary
*.woff  binary
*.woff2 binary
*.ttf   binary
*.eot   binary
*.vsix  binary
*.zip   binary
*.tar   binary
*.gz    binary
*.7z    binary
*.pdf   binary
```

After writing, print:
```
✅ git-sanitize: .gitattributes created/updated — eol=lf enforced
```

---

## Step 3 — Enable long paths

Desired value: `core.longpaths=true` at repo level (never `--global`). Check first:

```bash
git -C "$REPO_ROOT" config --local --get core.longpaths
```

If already `true`: silent (session-start mode) or `✅ git-sanitize: core.longpaths already enabled` (explicit invocation). Skip to Step 4.

Otherwise call `AskUserQuestion`:
- question: `"core.longpaths is not enabled in this repo. Set it to true?"`
- header: `"Long paths"`
- options: `"Yes, enable"` / `"No, skip"`

On yes:
```bash
git -C "$REPO_ROOT" config --local core.longpaths true
```
and print `✅ git-sanitize: core.longpaths=true set (repo-level)`.

---

## Step 4 — Detect CRLF-contaminated tracked files

```bash
git -C "$REPO_ROOT" ls-files \
  | xargs -I{} sh -c 'file "$REPO_ROOT/{}" 2>/dev/null | grep -q CRLF && echo "{}"'
```

Collect all matching paths as `CRLF_FILES`.

### If no files found

Silent (session-start mode) or print `✅ git-sanitize: no CRLF files found` (explicit invocation). Then skip to Step 6.

### If files found

Print a report:

```
⚠️  git-sanitize: N tracked file(s) with CRLF line endings found:

  client/tools/sidecar/main.py
  client/vscode/esbuild.config.js
  ...
```

Then call `AskUserQuestion`:
- question: `"N tracked file(s) have CRLF line endings. Normalize all to LF?"`
- header: `"CRLF → LF"`
- options: `"Yes, normalize all"` / `"No, skip"`

On no: skip Step 5 and continue with Step 6.

---

## Step 5 — Normalize (if confirmed)

For each file in `CRLF_FILES`:

```bash
sed -i 's/\r$//' "$REPO_ROOT/$file"
```

`sed -i` keeps the file mode, so the execute bit is preserved. Then stage only those files:

```bash
git -C "$REPO_ROOT" add -- $CRLF_FILES
```

Print:
```
✅ git-sanitize: N file(s) normalized and staged.

Next step: commit the normalization
  git commit -m "chore(git): normalize CRLF to LF across tracked files"
```

---

## Step 6 — Ensure execute bit on scripts

Tracked files that start with a shebang (`#!`) must be executable (mode `100755`).

```bash
git -C "$REPO_ROOT" ls-files -s | awk '$1=="100644"{print $4}' | while read -r f; do
  head -c2 "$REPO_ROOT/$f" 2>/dev/null | grep -q '^#!' && echo "$f"
done
```

Collect as `NON_EXEC_FILES`. If empty, skip (silent, or `✅ git-sanitize: execute bits OK` on explicit invocation). Otherwise list them and call `AskUserQuestion`:
- question: `"N script(s) with a shebang lack the execute bit. Mark them +x?"`
- header: `"Execute bit"`
- options: `"Yes, mark +x"` / `"No, skip"`

On yes, for each:

```bash
git -C "$REPO_ROOT" update-index --chmod=+x -- "$file"
chmod +x "$REPO_ROOT/$file" 2>/dev/null || true
```

`update-index` fixes the index even on filesystems without mode support (`/mnt/c`, Windows). Never remove an execute bit that is already set.

Print (if any): `✅ git-sanitize: N script(s) marked executable (+x)`. Otherwise silent (session-start) or `✅ git-sanitize: execute bits OK` (explicit).

---

## Step 7 — Encoding and BOM

Policy: `*.ps1` → UTF-8 **with** BOM; every other text file → UTF-8 **without** BOM. Skip binary files (`grep -Iq . "$file"` fails) and empty files.

BOM bytes: `EF BB BF`.

```bash
git -C "$REPO_ROOT" ls-files | while read -r f; do
  p="$REPO_ROOT/$f"; [ -s "$p" ] && grep -Iq . "$p" || continue
  has_bom=$(head -c3 "$p" | od -An -tx1 | tr -d ' \n' | grep -c '^efbbbf$')
  case "$f" in
    *.ps1) [ "$has_bom" = 0 ] && echo "ADD $f" ;;
    *)     [ "$has_bom" = 1 ] && echo "STRIP $f" ;;
  esac
done
```

Collect the `ADD`/`STRIP` lists. If both are empty, skip (silent, or `✅ git-sanitize: encoding OK`). Otherwise list the files and call `AskUserQuestion`:
- question: `"N file(s) violate the BOM policy (*.ps1 with BOM, others without). Fix them?"`
- header: `"Encoding"`
- options: `"Yes, fix"` / `"No, skip"`

On yes, apply:

- `ADD`: `printf '\xEF\xBB\xBF' | cat - "$p" > "$p.tmp" && cat "$p.tmp" > "$p" && rm "$p.tmp"` (keeps file mode).
- `STRIP`: `sed -i '1s/^\xEF\xBB\xBF//' "$p"`.
- Then `git add` only the modified files.

Non-UTF-8 detection (**report only, never convert** — the source encoding is unknown):

```bash
file --mime-encoding "$p"   # anything other than utf-8, us-ascii, binary → warn
```

Print (if any): `✅ git-sanitize: BOM fixed in N file(s) (+BOM ps1 / -BOM others)` and, for non-UTF-8 files, `⚠️  git-sanitize: non-UTF-8 file (not converted): <path> (<encoding>)`. Otherwise silent (session-start) or `✅ git-sanitize: encoding OK` (explicit).

---

## Step 8 — Summary (explicit invocation only)

When invoked as `/p4cc-core:git-sanitize`, always print a closing summary:

```
══════════════════════════════════════════
  git-sanitize COMPLETE
══════════════════════════════════════════
  Repo:              <REPO_ROOT>
  .gitattributes:    ✅ compliant  |  ⚠️ created
  core.longpaths:    ✅ true  |  ⚠️ set
  CRLF files found:  N
  CRLF files fixed:  N
  Scripts made +x:   N
  BOM fixed:         N
  Non-UTF-8 files:   N (reported)
══════════════════════════════════════════
```
