---
name: check
description: Read-only verification of the p4cc-core infrastructure — folders, files, external tools and plugin resources. Reports status and tells how to install anything missing. Also invoked explicitly as /p4cc-core:check.
version: 31
allowed-tools: [Bash]
---

# p4cc-core Check

Verifies that the whole infrastructure required by p4cc-core is in place: folders and files, external tools and the plugin's own resources. **Read-only** — never creates, modifies or installs anything. For each problem it prints how to fix it. Safe to re-run at any time.

---

## Step 1 — Read requirements from catalog

```bash
CATALOG=~/.p4cc/catalog.json
# Fallback: marketplace install path (used before ~/.p4cc/catalog.json is created)
[ ! -f "$CATALOG" ] && CATALOG=~/.claude/plugins/marketplaces/plugin4cc/specs/catalog.json
```

Read `catalog["plugins"]["p4cc-core"]["dependencies"]` and the `dependencies` of each of its skills. Collect the deduplicated list, preserving each `type`. If the catalog cannot be found, fall back to the tables below.

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

```bash
# Catalog copy must exist and be valid JSON
python3 -c "import json,os; json.load(open(os.path.expanduser('~/.p4cc/catalog.json')))" 2>&1 \
  || echo "invalid-or-missing"

# Marketplace source (to detect an outdated copy)
_src=$(find ~/.claude/plugins/marketplaces -path "*/plugin4cc*/specs/catalog.json" 2>/dev/null | head -1)
[ -n "$_src" ] && ! diff -q "$_src" ~/.p4cc/catalog.json >/dev/null 2>&1 && echo "outdated"
```

- Missing / invalid catalog → ❌, fix: `/p4cc-core:install`
- Copy differs from the marketplace one → ⚠️ outdated, fix: `/p4cc-core:install`

Any ❌ here is fixed by running `/p4cc-core:install`.

---

## Step 3 — Check plugin resources

The plugin ships no extra resource files. Only check that the plugin cache exists:

```bash
ls -d ~/.claude/plugins/cache/plugin4cc/p4cc-core/*/ 2>/dev/null || echo "❌ plugin cache not found"
```

If missing: `claude plugins install p4cc-core`.

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
| `tool` | `git` | `*` | `git-commit` |

```bash
which git && git --version 2>&1
```

---

## Step 5 — Print status report

```
══════════════════════════════════════════
  p4cc-core CHECK
══════════════════════════════════════════
```

One table per area (Folders, Plugin resources, Tools):

| Area | Item | Required | Found | Status |
|------|------|----------|-------|--------|
| folder | `~/.p4cc/` | exists | exists | ✅ |
| tool | `git` | `*` | — | ❌ |

- ✅ = present and version constraint satisfied
- ❌ = missing or below the minimum version
- ⚠️ = optional component missing, or outdated copy

---

## Step 6 — How to install what is missing

For each ❌ / ⚠️ item print the matching fix. **Never run these commands yourself** — only show them.

**Folders / catalog:** run `/p4cc-core:install`.

### `git`

**Debian / Ubuntu / WSL:**
```bash
sudo apt install git
```

**RHEL / Fedora:**
```bash
sudo dnf install git
```

**macOS:**
```bash
brew install git
```

**Windows (PowerShell):**
```powershell
winget install Git.Git
```

---

## Step 7 — Verdict

All required items ✅:
```
✅ p4cc-core infrastructure is complete. No action required.
```

Any required item ❌:
```
❌ N item(s) missing. Apply the fixes above, then re-run /p4cc-core:check.
```
