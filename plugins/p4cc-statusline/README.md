# p4cc-statusline

Visual enhancement plugin for Claude Code. Replaces the default statusline with a color-coded bar showing project context, git branch, active model and usage metrics.

## Result

```
~/your/project  ⎇ main ◌2 ●3 ⇡1  Sonnet 5.5 (medium)  CX16% SN88% WK8%
```

| Segment | Color | Description |
|---------|-------|-------------|
| `path` | 🟡 Yellow block | Project directory, home collapsed to `~` |
| `⎇ branch` | 🔵 Cyan block | Current git branch / worktree (omitted outside a git repo), followed by git state indicators; each one is hidden when its count is 0: `◌N` untracked files (not ignored) · `●N` changed files (staged or unstaged) · `⇡N` commits not yet pushed |
| `Model (effort)` | 🟣 Purple block | Active model display name, followed by the effort level in parentheses when available (e.g. `Sonnet 5.5 (medium)`) |
| `CX%` | 🟢/🟡/🔴 | Context window usage |
| `SN%` | 🟢/🟡/🔴 | 5-hour session rate limit |
| `WK%` | 🟢/🟡/🔴 | 7-day weekly rate limit |

The path, branch and model segments are colored blocks (reverse video). Usage values are colored by threshold: green (≤40%) · yellow (≤75%) · red (>75%).

If the line does not fit the terminal width, the path is shortened with `…` from the highest directory level to the lowest (`~/…/projects/personal/plugin4cc` → `~/…/…/personal/plugin4cc` → `~/…/…/…/plugin4cc`); the last level is never replaced. If even that does not fit, all hidden levels collapse into `… …` (`~/… …/plugin4cc`).

## Skills

| Skill | Invocation | What it does |
|-------|-----------|--------------|
| `install` | `/p4cc-statusline:install` · once after install | Installs script and activates statusline |

## Installation

```bash
claude plugins marketplace add rmompo/plugin4cc
claude plugins install p4cc-statusline
/p4cc-statusline:install
```

## Notes

- Pairs well with [`p4cc-core`](../p4cc-core/README.md) but works standalone.
