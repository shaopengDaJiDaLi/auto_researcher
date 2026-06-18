---
name: progress-report
description: "Generate structured research progress reports"
---

# progress-report

Generate a structured progress report for the current research project.

Invoke as `/progress-report` in Claude Code or `$progress-report` in Codex.

## Behavior

1. Read `workspace/experiments.jsonl` for cycle history, status, metrics, PID/log files, and conclusions
2. Read `workspace/MEMORY_LOG.md` for compact milestones and decisions
3. Read `workspace/DEAD_ENDS.md` and `workspace/INSIGHTS.md` for durable lessons
4. Check recent experiment logs referenced by the ledger or `workspace/state.json`
5. Compile results into a structured report

## Output Format

```markdown
# Progress Report — YYYY-MM-DD

## Current Status
- Best result: [metric]
- Total experiments: [N]
- Current direction: [description]

## Recent Experiments
| Cycle | Status | Hypothesis | Metrics | Log | Notes |
|-------|--------|------------|---------|-----|-------|

## Key Insights
- What we learned
- What works / doesn't work

## Dead Ends
- Approaches that should not be retried

## Next Steps
1. Planned experiments
2. Open questions

## Blockers
- Any issues or risks
```
