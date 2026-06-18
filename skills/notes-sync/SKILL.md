---
name: notes-sync
description: "Refresh notes dashboard and daily notes from current experiment state"
---

# notes-sync

Refresh progress notes for an Auto Researcher project.

## Usage

```bash
Claude Code: /notes-sync --project /path/to/project
Claude Code: /notes-sync --project /path/to/project --dashboard-only
Claude Code: /notes-sync --project /path/to/project --daily-only
Codex: $notes-sync
```

## Behavior

1. Read project config and check `notes.enabled`
2. Read `PROJECT_BRIEF.md`, `workspace/MEMORY_LOG.md`, `workspace/state.json`, `.cycle_counter`, `workspace/experiments.jsonl`, `workspace/DEAD_ENDS.md`, and `workspace/INSIGHTS.md`
3. Refresh `Dashboard.md` in notes, or `workspace/progress_tracking/Dashboard.txt` if no vault is configured
4. Optionally append a new daily note entry

The dashboard should reflect the current controlled-launch state: active PID,
log file, terminal state, recent ledger metrics, strategy-routed idea/code
handoffs, dead ends, and durable insights.

## Command

```bash
python -m auto_researcher.notes --project /path/to/project
```

If progress export is disabled, tell the user to set `notes.enabled: true`. If `notes.vault_path` is empty, notes fall back to project-local text files.
