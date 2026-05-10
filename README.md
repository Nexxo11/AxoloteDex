# AxoloteDex

> Safe species editing for `pokeemerald-expansion`.

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-2ea44f)
![Workflow](https://img.shields.io/badge/Workflow-Validate%20%E2%86%92%20Dry--Run%20%E2%86%92%20Apply-0A66C2)

AxoloteDex is a desktop tool focused on real production workflows: add, edit, and delete species with validation, dry-run planning, lint checks, backups, and rollback support.

---

## Table of Contents

- [Why AxoloteDex](#why-axolotedex)
- [Core Workflow](#core-workflow)
- [Features at a Glance](#features-at-a-glance)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Build](#build)
- [How to Use](#how-to-use)
- [Delete Modes](#delete-modes)
- [Rollback](#rollback)
- [Troubleshooting](#troubleshooting)
- [Expected Assets](#expected-assets)
- [Safety Notes](#safety-notes)

---

## Why AxoloteDex

Editing species manually across a `pokeemerald-expansion` codebase is error-prone. AxoloteDex reduces that risk by forcing a safe, inspectable change flow before any file write happens.

---

## Core Workflow

```text
Validate -> Generate DRY-RUN -> Review Plan -> Apply -> Build Check
```

Without `--apply`, AxoloteDex does not modify your target repository.

---

## Features at a Glance

| Area | What you get |
|---|---|
| Species editing | GUI editor with sprite preview |
| Change safety | Validation + lint gate before apply |
| Planning | `output/change_plan.md` and `output/change_plan.json` |
| Backup | Automatic backup before real writes (`backups/YYYYMMDD_HHMMSS/`) |
| Build confidence | Optional build check from GUI or CLI |
| Deletion control | `safe`, `replace+delete`, and `force-delete` modes |

---

## Requirements

- Python `3.10+` (recommended: `3.11` or `3.12`)
- A working `pokeemerald-expansion` project
- Linux/macOS: `make` available for build checks

---

## Quick Start

From the ASA project root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install dearpygui pillow
.venv/bin/python gui_app.py
```

---

## Build

### Windows build

Build the standalone app on a Windows machine:

```powershell
./scripts/build_windows.ps1
```

CMD alternative:

```bat
scripts\build_windows.bat
```

Expected output:

- `dist/AxoloteDex.exe`

Build notes:

- Uses `--onefile --windowed`.
- Build on Windows for native compatibility.

---

## How to Use

### GUI (recommended)

Run:

```bash
.venv/bin/python gui_app.py
```

Standard flow:

1. Select your `pokeemerald-expansion` path.
2. Choose an existing species or create a new one.
3. Click `Validate`.
4. Click `Generate DRY-RUN`.
5. Review warnings/errors/risk in the change plan.
6. Click `Apply changes`.
7. Run `Build project` (recommended).

Expected generated files after DRY-RUN:

- `output/change_plan.md`
- `output/change_plan.json`

Behavior details:

- If data changes after DRY-RUN, AxoloteDex can regenerate the plan before apply.
- Missing assets use fallback behavior and produce warnings.
- If lint fails, apply is blocked.

### CLI

#### 1) Analyze expansion structure

```bash
python3 analyze_expansion.py
```

#### 2) Export species

```bash
python3 export_species.py ./pokeemerald-expansion
```

Generated files:

- `output/species_index.json`
- `output/species_summary.md`
- `output/parse_warnings.md`

#### 3) DRY-RUN plan only

```bash
python3 apply_species_change.py <project_path> <change_file.json>
```

Example:

```bash
python3 apply_species_change.py ./pokeemerald-expansion examples/new_species.example.json
```

#### 4) Apply changes

```bash
python3 apply_species_change.py ./pokeemerald-expansion examples/new_species.example.json --apply
```

#### 5) Apply + build check

```bash
python3 apply_species_change.py ./pokeemerald-expansion examples/new_species.example.json --apply --build-check
```

Build artifacts:

- `output/build_log.txt`
- `output/build_summary.md`

---

## Delete Modes

- `safe`: blocks delete when external references are detected.
- `replace+delete`: attempts reference replacement, then deletes.
- `force-delete`: deletes even with remaining references (high risk).

Best practice: prefer `safe` or `replace+delete`, then run a build check.

---

## Rollback

Preview rollback (no writes):

```bash
python3 rollback_backup.py ./pokeemerald-expansion --latest --remove-path graphics/pokemon/testmon
```

Apply rollback:

```bash
python3 rollback_backup.py ./pokeemerald-expansion --latest --remove-path graphics/pokemon/testmon --apply
```

`--remove-path` is useful to clean folders created by newly added species.

---

## Troubleshooting

Run these commands when something looks wrong:

```bash
# Editor safety tests
python3 -m unittest tests.test_species_editor_safety -v

# GUI dry-run tests (requires dearpygui)
python3 -m unittest tests.test_gui_dry_run -v

# Launch GUI
.venv/bin/python gui_app.py

# Verify expansion build
make -j$(nproc)
```

Check these files first:

- `output/change_plan.md`
- `output/change_plan.json`
- `output/lint_report.md`
- `output/build_log.txt`
- `output/build_summary.md`

---

## Expected Assets

Species asset folder should include:

- `front.png`
- `back.png`
- `icon.png`
- `footprint.png`
- `normal.pal`
- `shiny.pal`

If files are missing, fallback assets are used and warnings are recorded.

---

## Safety Notes

- No `--apply` means no file writes.
- With `--apply`, backup is always created first.
- Parser is block/regex-based (not a full C parser).
- Complex macro patterns may emit warnings instead of hard failures.

---

## Version

Current GUI label: `AxoloteDex v0.6.0`.
