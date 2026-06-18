---
name: experiment-status
description: "Check status of running autonomous experiment loops"
---

# experiment-status

Check the current status of your autonomous experiment agent.

## Usage

```
Claude Code: /experiment-status
Claude Code: /experiment-status --project /path/to/project
Codex: $experiment-status
```

## Behavior

1. Read `PROJECT_BRIEF.md` — show the research goal
2. Read `workspace/state.json` — show current phase, PID, log file, terminal state, and last error
3. Read `workspace/experiments.jsonl` — show recent cycles, status, metrics, and conclusions
4. Read `workspace/MEMORY_LOG.md`, `workspace/DEAD_ENDS.md`, and `workspace/INSIGHTS.md`
5. Read `.cycle_counter` — show how many cycles completed
6. Check for running training via the configured execution backend using the state PID/log file
7. If training is running, tail the configured log file for latest output
8. Show GPU utilization through the configured backend
9. Check if `workspace/HUMAN_DIRECTIVE.md` exists (pending directive)

If `execution.mode=ssh`, controller state still comes from the local project
directory, but PID checks, training logs, and GPU status come from the
configured remote host.

In hybrid Codex mode, code modification may be done by `codex_cli`, but running
training should still appear as a framework `launch_experiment` result with
authoritative `pid` and `log_file` in `state.json`.

## Output Format

```markdown
# Experiment Status — my-project

## Goal
Train ViT-B/16 on ImageNet to 78%+ accuracy

## Progress
- Cycles completed: 4
- Current best: 78.3% (Exp004, ViT-B/16 + cosine + mixup)
- Status: TRAINING (PID 12345, GPU 0, running 3.2h)

## Latest Training Log
Epoch 45/90 | loss: 2.134 | acc: 77.1% | lr: 1.2e-4

## Recent Decisions
1. [04-08 14:45] Target reached with mixup, trying stronger augmentation
2. [04-08 06:00] Cosine schedule helped, adding regularization

## Recent Ledger
- cycle 4 [completed] mixup + cosine (acc=78.3) -> target reached
- cycle 5 [running] stronger augmentation (no metrics yet)

## Pending Directive
None (drop a file at workspace/HUMAN_DIRECTIVE.md to intervene)
```
