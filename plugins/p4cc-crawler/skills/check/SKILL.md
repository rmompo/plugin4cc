---
name: check
description: Read-only verification of the p4cc-crawler infrastructure — folders, files, external tools and plugin resources. Reports status and tells how to install anything missing. Also invoked explicitly as /p4cc-crawler:check.
version: 3
allowed-tools: [Bash]
---

# p4cc-crawler Check

Verifies that the whole infrastructure required by p4cc-crawler is in place: folders and files, external tools and the plugin's own resources. **Read-only** — never creates, modifies or installs anything. For each problem it prints how to fix it. Safe to re-run at any time.

---

## Step 1 — Read requirements from catalog

```bash
CATALOG=~/.p4cc/catalog.json
# Fallback: marketplace install path (used before ~/.p4cc/catalog.json is created)
[ ! -f "$CATALOG" ] && CATALOG=~/.claude/plugins/marketplaces/plugin4cc/specs/catalog.json
```

Read `catalog["plugins"]["p4cc-crawler"]["dependencies"]` and the `dependencies` of each of its skills. Collect the deduplicated list, preserving each `type`. If the catalog cannot be found, fall back to the tables below.

---

## Step 2 — Check folders and files

| Path | Purpose |
|------|---------|
| `~/.p4cc/` | global p4cc data folder |
| `~/.p4cc/catalog.json` | marketplace catalog copy (file) |

```bash
[ -d ~/.p4cc/ ] && echo "✅ ~/.p4cc/" || echo "❌ ~/.p4cc/"
[ -f ~/.p4cc/catalog.json ] && echo "✅ ~/.p4cc/catalog.json" || echo "❌ ~/.p4cc/catalog.json"
```

No plugin-specific folders: each crawl session writes to the output folder chosen at runtime by `/p4cc-crawler:extract`.

Any ❌ here is fixed by running `/p4cc-crawler:install`.

---

## Step 3 — Check plugin resources

Files shipped with the plugin must be present in the plugin cache:

```bash
PLUGIN_CACHE=$(ls -d ~/.claude/plugins/cache/plugin4cc/p4cc-crawler/*/ 2>/dev/null | sort -V | tail -1)
[ -z "$PLUGIN_CACHE" ] && echo "❌ plugin cache not found"
for f in scripts/crawl.py scripts/dedup.py scripts/download.py scripts/filter.py scripts/generate.py; do
  [ -f "$PLUGIN_CACHE$f" ] && echo "✅ $f" || echo "❌ $f"
done
```

A ❌ here means a broken or partial plugin install — fix with:

```bash
claude plugins update p4cc-crawler
```

---

## Step 4 — Check external tools

For each dependency, check by type:

| Type | How to check |
|------|-------------|
| `tool` | `which <name> 2>/dev/null && <name> --version 2>&1 \| head -1` — then verify the version constraint |
| `plugin` | `ls ~/.claude/plugins/cache/plugin4cc/<name>/ 2>/dev/null` — installed if the directory has at least one entry |

Currently required:

| Type | Name | Required | Used by |
|------|------|----------|---------|
| `tool` | `python3` | `>=3.8.0` | all scripts |
| `tool` | `curl` | `*` | `extract` (static sites) |

```bash
which python3 && python3 --version 2>&1
which curl && curl --version | head -1 2>&1
```

### Python packages

Not system binaries — checked separately:

```bash
python3 -c "import bs4; print(getattr(bs4, '__version__', 'ok'))" 2>/dev/null
python3 -c "import html2text; print(getattr(html2text, '__version__', 'ok'))" 2>/dev/null
python3 -c "import playwright; print(getattr(playwright, '__version__', 'ok'))" 2>/dev/null
```

| Package | Level |
|---------|-------|
| `beautifulsoup4` | required |
| `html2text` | required |
| `playwright` | optional (SPA mode) |

Optional packages missing → ⚠️ (does not fail the check).

---

## Step 5 — Print status report

```
══════════════════════════════════════════
  p4cc-crawler CHECK
══════════════════════════════════════════
```

One table per area (Folders, Plugin resources, Tools, Python packages):

| Area | Item | Required | Found | Status |
|------|------|----------|-------|--------|
| folder | `~/.p4cc/` | exists | exists | ✅ |
| tool | `python3` | `>=3.8.0` | — | ❌ |

- ✅ = present and version constraint satisfied
- ❌ = missing or below the minimum version
- ⚠️ = optional component missing, or outdated copy

---

## Step 6 — How to install what is missing

For each ❌ / ⚠️ item print the matching fix. **Never run these commands yourself** — only show them.

**Folders / catalog:** run `/p4cc-crawler:install`.

### `python3`

**Bash (Linux/WSL):**
```bash
sudo apt install python3
```

**PowerShell (Windows):**
```powershell
winget install Python.Python.3
```

### `curl`

**Bash (Linux/WSL):**
```bash
sudo apt install curl
```

**PowerShell (Windows):**
```powershell
winget install cURL.cURL
```

### `beautifulsoup4` (required)

```bash
pip install beautifulsoup4
```

### `html2text` (required)

```bash
pip install html2text
```

### `playwright` (optional (SPA mode))

```bash
pip install playwright && playwright install chromium
```

---

## Step 7 — Verdict

All required items ✅:
```
✅ p4cc-crawler infrastructure is complete. No action required.
```

Any required item ❌:
```
❌ N item(s) missing. Apply the fixes above, then re-run /p4cc-crawler:check.
```
