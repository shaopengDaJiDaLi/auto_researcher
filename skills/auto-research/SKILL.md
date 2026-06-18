---
name: auto-research
description: "Launch or resume an Auto Researcher autonomous GPU experiment loop. Use for 24/7 research automation, Codex/Claude hybrid provider setup, controlled training launch with PID/log monitoring, strategy-routed idea/code/writing roles, or zero-LLM experiment monitoring."
---

# auto-research

Launch an autonomous experiment agent that runs deep learning experiments 24/7.

## What This Does

This skill starts a **THINK -> STRATEGY ROUTING -> EXECUTE -> MONITOR -> REFLECT** loop:

1. Read `PROJECT_BRIEF.md`, `MEMORY_LOG.md`, ledger, journals, state, and directives.
2. Use the Leader to plan the next action.
3. Apply deterministic strategy routing when ideation or handoff rules require it.
4. Dispatch exactly one worker for the cycle: `idea`, `code`, or `writing`.
5. For code work, prefer Codex CLI for code modification and framework-controlled launch.
6. Run dry-run and `launch_experiment` through the framework so PID/log tracking is authoritative.
7. Monitor training at zero LLM cost.
8. Reflect on the result, update memory/ledger/journals, and repeat.

## Usage

```
Claude Code: /auto-research
Claude Code: /auto-research --project /path/to/my_project --gpu 0
Claude Code: /auto-research --project . --max-cycles 5
Codex: $auto-research
```

## Prerequisites

The project directory must contain:

### `PROJECT_BRIEF.md` (required)
A frozen reference describing your research goal. Example:

```markdown
# Goal
Train a ViT-B/16 on ImageNet to reach 78%+ top-1 accuracy.

# Codebase
- Training: train.py
- Config: configs/vit_base.yaml
- Data: /data/imagenet/

# Constraints
- GPU 0-3 available (use DDP)
- Max 90 epochs per run
- Report val accuracy after each run

# Current Best
- ResNet-50 baseline: 76.1%
```

### `config.yaml` (optional)
Override default agent settings:

```yaml
agent:
  provider: "openai"              # fallback for roles not overridden
  model: "gpt-5.4"
  api_key_env: "OPENAI_API_KEY"

  leader_provider: "codex_cli"
  reflect_provider: "codex_cli"
  code_modify_provider: "codex_cli"
  code_launch_provider: "builtin" # framework runs dry-run + launch_experiment
  idea_provider: "openai"         # keeps literature tools under ResearchToolRegistry
  writing_provider: "openai"

  max_cycles: -1                  # -1 = unlimited
  cooldown_interval: 300          # 5 min smart polling

strategy:
  enabled: true
  require_initial_ideation: true
  stagnation_cycles_before_idea: 3
  idea_to_code_handoff: true
  require_dry_run: true
  dry_run_timeout: 300

ledger:
  enabled: true
  metric_key: ""                  # set this to enable metric-based stagnation

memory:
  brief_max_chars: 3000
  log_max_chars: 2000

monitor:
  poll_interval: 900      # check every 15 min during training
  zero_llm: true

experiment:
  mandatory_dry_run: true
```

If the user wants a compatible cloud API endpoint instead of the official Anthropic
or OpenAI API, keep `provider: "openai"` and set `base_url` plus a custom
`api_key_env`, or use the built-in cloud presets `deepseek`, `qwen`, `kimi`, or `glm`.

Optional remote execution over SSH:

```yaml
execution:
  mode: "ssh"
  ssh_host: "user@server"
  remote_workspace: "/home/user/my_project/workspace"
  remote_python: "python3"
```

In SSH mode, the controller state stays local (`PROJECT_BRIEF.md`,
`workspace/MEMORY_LOG.md`, `workspace/HUMAN_DIRECTIVE.md`, `state.json`),
while code edits, shell commands, training, log tailing, PID checks, and GPU
queries run on the configured remote host.

## Workflow Details

### Phase 1: THINK
- Read `PROJECT_BRIEF.md` (frozen, max 3000 chars)
- Read `MEMORY_LOG.md` (rolling, auto-compacted)
- Read recent ledger entries, dead ends, insights, safety violations, and phase gate signals when enabled
- Check for `HUMAN_DIRECTIVE.md` (highest priority, auto-archived after reading)
- Analyze: What's the current best? What hasn't been tried? What's most promising?
- Output: JSON plan with `action`, `agent`, `task`, `hypothesis`, and success criteria

### Phase 2: STRATEGY ROUTING
- If `require_initial_ideation` is enabled and no idea cycle exists, route to `idea`
- If the human directive asks for papers/literature/arXiv, route to `idea`
- If stagnation reaches `stagnation_cycles_before_idea`, route to `idea`
- If the previous ledger status was `idea` and `idea_to_code_handoff` is enabled, route to `code`

### Phase 3: EXECUTE
- `idea`: use literature tools (`search_papers`, `search_arxiv`, `get_paper`) and write actionable hypotheses
- `writing`: read results and write reports
- `code` in hybrid mode:
  1. `code_modify_provider` (usually `codex_cli`) inspects and edits the repo
  2. It must not start long-running training
  3. It returns one handoff JSON object:

```json
{
  "status": "ready_to_launch",
  "changed_files": ["relative/path.py"],
  "dry_run_command": "python train.py --max_steps 2",
  "launch_command": "python train.py --config configs/exp.yaml",
  "log_file": "logs/exp_001.log",
  "expected_duration": "about 8 hours"
}
```

### Phase 4: FRAMEWORK LAUNCH + MONITOR
- The framework runs `dry_run_command` via `run_shell`
- If dry-run fails or is missing while `require_dry_run: true`, training is not launched
- The framework runs `launch_command` via `launch_experiment`
- `launch_experiment` is the authoritative source for `pid` and `log_file`
- Training is monitored at zero LLM cost:
  - backend PID check — is process alive?
  - backend `nvidia-smi` — GPU utilization
  - backend `tail -50 logfile` — latest training output

### Phase 5: REFLECT
- Parse training logs for metrics (loss, accuracy, FGD, FID, etc.)
- Compare against previous best
- Record the cycle in `workspace/experiments.jsonl`
- Log milestone/decision in `MEMORY_LOG.md`
- Append durable insights/dead ends when useful
- Decide: try another config / pivot direction / generate report

### Human Override (anytime)
```bash
# Drop a directive file — agent reads it next cycle with highest priority
echo "Try learning rate 1e-5 with cosine schedule" > workspace/HUMAN_DIRECTIVE.md
```

## Memory System

The loop combines compact memory with append-only history:

| File | Content |
|------|---------|
| `PROJECT_BRIEF.md` | Frozen project reference |
| `workspace/MEMORY_LOG.md` | Compact key results and recent decisions |
| `workspace/experiments.jsonl` | Append-only cycle ledger |
| `workspace/DEAD_ENDS.md` | Approaches not to retry |
| `workspace/INSIGHTS.md` | Durable findings |
| `workspace/state.json` | Current cycle/status/PID/log state |

`MEMORY_LOG.md` stays compact; ledger and journals preserve long-running history.

## Cost

| Phase | Duration | LLM Cost |
|-------|----------|----------|
| THINK / routing | minutes | LLM or subscription |
| EXECUTE code modify | minutes | LLM or subscription |
| MONITOR training | hours/days | **$0.00** |
| REFLECT | minutes | LLM or subscription |
| **24h cycle total** | | **~$0.08** |

## Example Output

After a few cycles, your `workspace/MEMORY_LOG.md` will look like:

```markdown
# Memory Log

## Key Results
[04-07 14:30] Exp001: ResNet-50 baseline, lr=0.1, acc=76.1%
[04-07 22:15] Exp002: ViT-B/16, lr=1e-3, acc=74.8% (underperforming, lr too high)
[04-08 06:00] Exp003: ViT-B/16, lr=3e-4 + cosine, acc=77.9% (new best!)
[04-08 14:45] Exp004: ViT-B/16, lr=3e-4 + cosine + mixup, acc=78.3% (target reached!)

## Recent Decisions
[04-07 14:30] Start with ResNet-50 baseline to establish reference
[04-07 22:15] ViT lr=1e-3 too high, try 3e-4 next
[04-08 06:00] Cosine schedule helped significantly, try adding regularization
[04-08 14:45] Target reached! Generate final report.
```
