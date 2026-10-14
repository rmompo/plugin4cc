# Plugin Spec: p4cc-statusline

> **Status:** `stable` | **Version:** `1.0.4`

---

## Overview

`p4cc-statusline` is a Claude Code visual enhancement plugin. It replaces the default statusline with a custom color-coded bar that surfaces project context, git state, active model and usage metrics at a glance.

It is intentionally decoupled from `p4cc-core` — it can be installed standalone or alongside any other plugin.

---

## Skill: `install`

### Purpose

Install the statusline script and activate it in Claude Code's settings. Runs automatically at session start via the plugin's default agent. The `/p4cc-statusline:install` skill is available as a manual fallback or for reinstallation.

### Invocation

```bash
/p4cc-statusline:install    # manual install or reinstall
```

### Auto-setup behavior

The `p4cc-statusline` agent (activated via `settings.json`) checks at session start:

1. Is `~/.claude/statusline-command.sh` present and matches the plugin source?
2. Does `~/.claude/settings.json` have `statusLine` pointing to it?

If all conditions are met → silent, no action.
If any condition fails → installs/updates automatically and reports briefly.

### Statusline output

```
⌂ ~/your/project  ⎇ main  ✦ Sonnet 5.5 (medium)  CX16% SN88% WK8%
```

| Segment | Color | Source |
|---------|-------|--------|
| `⌂ path` | Yellow | `workspace.project_dir`, home-collapsed |
| `⎇ branch` | Cyan | Git branch / worktree name (omitted outside a git repo) |
| `✦ model (effort)` | Purple | `model.display_name` + `effort.level` (effort omitted if the model does not support it) |
| `CX%` | Green/Yellow/Red | `context_window.used_percentage` |
| `SN%` | Green/Yellow/Red | `rate_limits.five_hour.used_percentage` |
| `WK%` | Green/Yellow/Red | `rate_limits.seven_day.used_percentage` |

Color thresholds: ≤40% green · ≤75% yellow · >75% red.

Path shortening: when the line does not fit the terminal width, only the `⌂ path` segment is shortened. Directory levels are replaced by `…` from the highest (closest to root) to the lowest, one at a time, until it fits: `~/a/b/c/proj` → `~/…/b/c/proj` → `~/…/…/c/proj` → `~/…/…/…/proj`. The last level is never replaced.

### Non-Goals
- Does not modify any project files
- Does not affect Claude's behavior or responses

---

## Changelog

| Version | Changes |
|---------|---------|
| 1.0.4 | statusline: shorten the CWD with … (highest level first, last level never) when the line does not fit the terminal width |
| 1.0.3 | statusline: show effort level in parentheses after the model name |
| 1.0.1 | Version alignment to Z system |
| 1.0.0 | Initial release — renamed from p4-statusline, skill setup→statusline |
