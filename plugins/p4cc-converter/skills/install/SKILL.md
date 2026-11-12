---
name: install
description: Installs the p4cc-converter infrastructure — creates the required folders and files — then runs the check. Tools are never installed automatically; missing ones are reported with install instructions. Also invoked explicitly as /p4cc-converter:install.
version: 7
allowed-tools: [Bash]
---

# p4cc-converter Install

Creates the folders and files p4cc-converter needs, then verifies the result with `/p4cc-converter:check`. Idempotent — safe to re-run at any time. External tools are **not** installed automatically: `/p4cc-converter:check` reports each missing one with its install command.

---

## Step 1 — Install / update ~/.p4cc/catalog.json

Copy the latest `catalog.json` from the marketplace to the global user path.

```bash
_src=$(find ~/.claude/plugins/marketplaces -path "*/plugin4cc*/specs/catalog.json" 2>/dev/null | head -1)
if [ -n "$_src" ]; then
  mkdir -p ~/.p4cc
  cp "$_src" ~/.p4cc/catalog.json
  echo "✅ ~/.p4cc/catalog.json installed from: $_src"
else
  echo "⚠️  Marketplace catalog not found — add the marketplace first:"
  echo "   claude plugins marketplace add rmompo/plugin4cc"
fi
```

---

## Step 2 — Verify

Run `/p4cc-converter:check` and show its report. If it lists missing tools, print their install instructions and ask the user to re-run `/p4cc-converter:check` once installed.
