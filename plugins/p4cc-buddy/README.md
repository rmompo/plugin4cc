# p4cc-buddy

<company>-specific skills for Claude Code. Tools to assist <company> employees with internal platform workflows.

## Skills

| Skill | Invocation | What it does |
|-------|-----------|--------------|
| `gcomp` | `/p4cc-buddy:gcomp [hint]` | Generates a ready-to-paste <hr-platform> mission report from the active project or a user hint |

## Installation

```bash
claude plugins marketplace add rmompo/plugin4cc
claude plugins install p4cc-buddy
```

## Usage

```bash
# Auto-infer from active workspace
/p4cc-buddy:gcomp

# With a hint
/p4cc-buddy:gcomp <project-hint>
```

The skill infers all mission fields automatically and confirms each section interactively before generating the final report.

## Notes

- Designed for <company> employees using the <hr-platform> competency management platform.
- Competency catalog includes all 145 official competency entries.
- Works standalone — no dependency on other p4 plugins.
