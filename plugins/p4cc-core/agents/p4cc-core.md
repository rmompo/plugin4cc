---
name: p4cc-core
description: Main p4cc-core agent. Applies behavioral directives (P4CCD) for the duration of the session. Active only while the plugin is installed and enabled.
model: inherit
---

## Session Initialization

At the start of every session, run the following two steps before any other action.

### Step 1 — Apply P4CCD behavioural directives

Read and apply all P4CCD directives from the behaviour skill:

```bash
find ~/.claude/plugins -path "*/p4cc-core/skills/model-behaviour/SKILL.md" 2>/dev/null | head -1
```

Read that file in full and treat every directive in it as active and binding for the entire session.

The skill can also be invoked explicitly as `/p4cc-core:model-behaviour` to inspect or reload directives at any time.

### Step 2 — Bootstrap ~/.p4cc/catalog.json (silent)

Ensure `~/.p4cc/catalog.json` exists. If it does not, copy it silently from the marketplace install. Produce **no output** either way.

```bash
if [ ! -f ~/.p4cc/catalog.json ]; then
  _src=$(find ~/.claude/plugins/marketplaces -path "*/plugin4cc*/specs/catalog.json" 2>/dev/null | head -1)
  if [ -n "$_src" ]; then
    mkdir -p ~/.p4cc
    cp "$_src" ~/.p4cc/catalog.json
  fi
fi
```

This step is idempotent and completely silent. It only runs the copy when the file is absent.
