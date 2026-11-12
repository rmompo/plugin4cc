---
name: check
description: Read-only verification of the p4cc-converter infrastructure — folders, files, external tools and plugin resources. Reports status and tells how to install anything missing. Also invoked explicitly as /p4cc-converter:check.
version: 7
allowed-tools: [Bash]
---

# p4cc-converter Check

Verifies that the whole infrastructure required by p4cc-converter is in place: folders and files, external tools and the plugin's own resources. **Read-only** — never creates, modifies or installs anything. For each problem it prints how to fix it. Safe to re-run at any time.

---

## Step 1 — Read requirements from catalog

```bash
CATALOG=~/.p4cc/catalog.json
# Fallback: marketplace install path (used before ~/.p4cc/catalog.json is created)
[ ! -f "$CATALOG" ] && CATALOG=~/.claude/plugins/marketplaces/plugin4cc/specs/catalog.json
```

Read `catalog["plugins"]["p4cc-converter"]["dependencies"]` and the `dependencies` of each of its skills. Collect the deduplicated list, preserving each `type`. If the catalog cannot be found, fall back to the tables below.

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

No plugin-specific folders: documents are converted in place, next to their source file.

Any ❌ here is fixed by running `/p4cc-converter:install`.

---

## Step 3 — Check plugin resources

Files shipped with the plugin must be present in the plugin cache:

```bash
PLUGIN_CACHE=$(ls -d ~/.claude/plugins/cache/plugin4cc/p4cc-converter/*/ 2>/dev/null | sort -V | tail -1)
[ -z "$PLUGIN_CACHE" ] && echo "❌ plugin cache not found"
for f in resources/scripts/all-to-md-consolidate.py; do
  [ -f "$PLUGIN_CACHE$f" ] && echo "✅ $f" || echo "❌ $f"
done
```

A ❌ here means a broken or partial plugin install — fix with:

```bash
claude plugins update p4cc-converter
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
| `tool` | `qpdf` | `>=10.0.0` | `any-to-md` |
| `tool` | `python3` | `>=3.8.0` | `any-to-md` |
| `tool` | `libreoffice` | `>=7.0.0` | `any-to-md` (non-PDF inputs only) |

```bash
which qpdf && qpdf --version | head -1 2>&1
which python3 && python3 --version 2>&1
which libreoffice && libreoffice --version | head -1 2>&1
```

---

## Step 5 — Print status report

```
══════════════════════════════════════════
  p4cc-converter CHECK
══════════════════════════════════════════
```

One table per area (Folders, Plugin resources, Tools):

| Area | Item | Required | Found | Status |
|------|------|----------|-------|--------|
| folder | `~/.p4cc/` | exists | exists | ✅ |
| tool | `qpdf` | `>=10.0.0` | — | ❌ |

- ✅ = present and version constraint satisfied
- ❌ = missing or below the minimum version
- ⚠️ = optional component missing, or outdated copy

---

## Step 6 — How to install what is missing

For each ❌ / ⚠️ item print the matching fix. **Never run these commands yourself** — only show them.

**Folders / catalog:** run `/p4cc-converter:install`.

### `qpdf`

**Debian / Ubuntu / WSL:**
```bash
sudo apt install qpdf
```

**RHEL / Fedora:**
```bash
sudo dnf install qpdf
```

**PowerShell (Windows):**
```powershell
winget install qpdf
```

### `python3`

**Debian / Ubuntu / WSL:**
```bash
sudo apt install python3
```

**RHEL / Fedora:**
```bash
sudo dnf install python3
```

**PowerShell (Windows):**
```powershell
winget install Python.Python.3
```

### `libreoffice`

**Debian / Ubuntu / WSL:**
```bash
sudo apt install libreoffice
```

**RHEL / Fedora:**
```bash
sudo dnf install libreoffice
```

**PowerShell (Windows):**
```powershell
winget install TheDocumentFoundation.LibreOffice
```

---

## Step 7 — Verdict

All required items ✅:
```
✅ p4cc-converter infrastructure is complete. No action required.
```

Any required item ❌:
```
❌ N item(s) missing. Apply the fixes above, then re-run /p4cc-converter:check.
```
