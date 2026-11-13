# p4cc-ccvv

AI-powered CV generation and management. Multi-user profile storage, job offer adaptation, and multi-format export (PDF, DOCX, HTML, MD).

## Storage

All data lives in `~/.p4cc/p4cc-ccvv/`:
```
~/.p4cc/p4cc-ccvv/
├── profiles.json           ← user registry
└── profiles/
    └── [user]/
        ├── input/          ← source CV files + photo
        ├── data/           ← profile.json, cvs.json
        └── output/         ← generated drafts and exports
```

## Skills

| Skill | Invocation | What it does |
|-------|------------|--------------|
| `install` | `/p4cc-ccvv:install` | Creates `~/.p4cc/`, `~/.p4cc/p4cc-ccvv/profiles/` and installs the marketplace `catalog.json` copy. Options: `--dry-run`, `--json`, `--home DIR`. |
| `check` | `/p4cc-ccvv:check` | Read-only check of folders, catalog, tools and shipped files; `STATE\|ID\|detail` lines, `--json`, exit codes. |
| `profile-gather` | `/p4cc-ccvv:profile-gather` | Extract profile data from a source CV file |
| `profile-update` | `/p4cc-ccvv:profile-update` | Update an existing profile with new data |
| `generate` | `/p4cc-ccvv:generate` | Generate an adapted CV draft for a job position |
| `regen` | `/p4cc-ccvv:regen` | Regenerate existing CV drafts with updated profile |
| `export` | `/p4cc-ccvv:export` | Export a draft to PDF, DOCX, HTML or MD |

## Typical workflow

```
1. /p4cc-ccvv:install           → create folders
   /p4cc-ccvv:check             → verify folders and tools
2. /p4cc-ccvv:profile-gather  → extract profile from your CV
3. /p4cc-ccvv:generate        → create adapted CV for a job offer
   (review and edit the generated draft)
4. /p4cc-ccvv:export          → produce final PDF/DOCX
```

## Installation

```bash
claude plugins marketplace add rmompo/plugin4cc
claude plugins install p4cc-ccvv
```

## Requirements

- Pandoc >=2.0.0
- pdflatex (TeX Live or MiKTeX)
- Python 3 >=3.10.0
