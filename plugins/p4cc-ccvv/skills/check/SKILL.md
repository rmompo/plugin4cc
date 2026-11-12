---
name: check
description: Read-only verification of the p4cc-ccvv infrastructure — folders, files, external tools and plugin resources. Reports status and tells how to install anything missing. Also invoked explicitly as /p4cc-ccvv:check.
version: 17
allowed-tools: [Bash]
---

# p4cc-ccvv Check

Verifies that the whole infrastructure required by p4cc-ccvv is in place: folders and files, external tools and the plugin's own resources. **Read-only** — never creates, modifies or installs anything. For each problem it prints how to fix it. Safe to re-run at any time.

---

## Step 1 — Read requirements from catalog

```bash
CATALOG=~/.p4cc/catalog.json
# Fallback: marketplace install path (used before ~/.p4cc/catalog.json is created)
[ ! -f "$CATALOG" ] && CATALOG=~/.claude/plugins/marketplaces/plugin4cc/specs/catalog.json
```

Read `catalog["plugins"]["p4cc-ccvv"]["dependencies"]` and the `dependencies` of each of its skills. Collect the deduplicated list, preserving each `type`. If the catalog cannot be found, fall back to the tables below.

---

## Step 2 — Check folders and files

| Path | Purpose |
|------|---------|
| `~/.p4cc/` | global p4cc data folder |
| `~/.p4cc/catalog.json` | marketplace catalog copy (file) |
| `~/.p4cc/p4cc-ccvv/` | ccvv storage root |
| `~/.p4cc/p4cc-ccvv/profiles/` | user profiles |

```bash
[ -d ~/.p4cc/ ] && echo "✅ ~/.p4cc/" || echo "❌ ~/.p4cc/"
[ -f ~/.p4cc/catalog.json ] && echo "✅ ~/.p4cc/catalog.json" || echo "❌ ~/.p4cc/catalog.json"
[ -d ~/.p4cc/p4cc-ccvv/ ] && echo "✅ ~/.p4cc/p4cc-ccvv/" || echo "❌ ~/.p4cc/p4cc-ccvv/"
[ -d ~/.p4cc/p4cc-ccvv/profiles/ ] && echo "✅ ~/.p4cc/p4cc-ccvv/profiles/" || echo "❌ ~/.p4cc/p4cc-ccvv/profiles/"
```

Each profile found under `~/.p4cc/p4cc-ccvv/profiles/<id>/` must contain `input/`, `data/` and `output/`:

```bash
for d in ~/.p4cc/p4cc-ccvv/profiles/*/; do
  [ -d "$d" ] || continue
  for s in input data output; do [ -d "$d$s" ] || echo "❌ $d$s missing"; done
done
```

An empty `profiles/` folder is fine (no profiles created yet) — report it as ℹ️, not ❌. Missing subfolders are repaired by `/p4cc-ccvv:profile-gather`, not by install.

Any ❌ here is fixed by running `/p4cc-ccvv:install`.

---

## Step 3 — Check plugin resources

Files shipped with the plugin must be present in the plugin cache:

```bash
PLUGIN_CACHE=$(ls -d ~/.claude/plugins/cache/plugin4cc/p4cc-ccvv/*/ 2>/dev/null | sort -V | tail -1)
[ -z "$PLUGIN_CACHE" ] && echo "❌ plugin cache not found"
for f in resources/CV-GENERATION-GUIDELINES.md resources/templates/cv-template.md resources/templates/cv-template-photo.md resources/templates/cv-template-nophoto.md resources/schemas/cvs.schema.json resources/schemas/profile.schema.json resources/schemas/profiles.schema.json; do
  [ -f "$PLUGIN_CACHE$f" ] && echo "✅ $f" || echo "❌ $f"
done
```

A ❌ here means a broken or partial plugin install — fix with:

```bash
claude plugins update p4cc-ccvv
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
| `tool` | `pandoc` | `>=2.0.0` | `export` |
| `tool` | `pdflatex` | `*` | `export` (PDF) |
| `tool` | `python3` | `>=3.8.0` | `profile-gather` |

```bash
which pandoc && pandoc --version | head -1 2>&1
which pdflatex && pdflatex --version | head -1 2>&1
which python3 && python3 --version 2>&1
```

---

## Step 5 — Print status report

```
══════════════════════════════════════════
  p4cc-ccvv CHECK
══════════════════════════════════════════
```

One table per area (Folders, Plugin resources, Tools):

| Area | Item | Required | Found | Status |
|------|------|----------|-------|--------|
| folder | `~/.p4cc/` | exists | exists | ✅ |
| tool | `pandoc` | `>=2.0.0` | — | ❌ |

- ✅ = present and version constraint satisfied
- ❌ = missing or below the minimum version
- ⚠️ = optional component missing, or outdated copy

---

## Step 6 — How to install what is missing

For each ❌ / ⚠️ item print the matching fix. **Never run these commands yourself** — only show them.

**Folders / catalog:** run `/p4cc-ccvv:install`.

### `pandoc`

**Bash (Linux/WSL):**
```bash
sudo apt install pandoc
```

**PowerShell (Windows):**
```powershell
winget install JohnMacFarlane.Pandoc
```

### `pdflatex`

**Bash (Linux/WSL):**
```bash
sudo apt install texlive-latex-base texlive-latex-recommended texlive-fonts-recommended
```

**PowerShell (Windows):**
```powershell
winget install MiKTeX.MiKTeX
```

### `python3`

**Bash (Linux/WSL):**
```bash
sudo apt install python3
```

**PowerShell (Windows):**
```powershell
winget install Python.Python.3
```

---

## Step 7 — Verdict

All required items ✅:
```
✅ p4cc-ccvv infrastructure is complete. No action required.
```

Any required item ❌:
```
❌ N item(s) missing. Apply the fixes above, then re-run /p4cc-ccvv:check.
```
