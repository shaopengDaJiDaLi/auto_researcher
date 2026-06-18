# Auto Researcher

<p align="center">
  <img src="assets/readme/hero.png" alt="Auto Researcher hero" width="900"/>
</p>

<p align="center">
  <strong>A cloud-API-first research operations loop for autonomous deep learning experiments.</strong>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> |
  <a href="#architecture">Architecture</a> |
  <a href="#configuration">Configuration</a> |
  <a href="#skills">Skills</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/cloud%20LLM%20API-only-0f766e.svg" alt="Cloud API only"/>
  <img src="https://img.shields.io/badge/Codex%20CLI-supported-111827.svg" alt="Codex CLI"/>
  <img src="https://img.shields.io/badge/Claude%20Code-supported-6d28d9.svg" alt="Claude Code"/>
  <img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License"/>
</p>

---

## What It Is

Auto Researcher runs the repetitive experiment-ops loop around machine learning research:

1. Read the project brief, memory, ledger, journals, and human directives.
2. Plan the next action with a leader role.
3. Route to exactly one worker role: `idea`, `code`, or `writing`.
4. For code work, let an agent edit the repo but keep training launch under framework control.
5. Dry-run, launch, monitor PID/log/GPU status, and reflect on the result.
6. Record the cycle and continue.

The key design choice is separation of responsibility: coding agents can modify files, but Auto Researcher owns dry-run, launch, PID/log tracking, and monitoring. That keeps the long-running experiment state observable and recoverable.

## What Changed In This Refactor

This project is the clean successor line to the old codebase:

- Runtime package: `auto_researcher/`
- Main entrypoint: `python -m auto_researcher.runner`
- Main skill: `/auto-research` for Claude Code, `$auto-research` for Codex
- Prompt directory: `prompts/`
- Progress export: `notes-sync`
- Cloud APIs only: no local LLM setup is required

## Quickstart

```bash
cd ~/project/auto_researcher
python install.py
python -m auto_researcher.runner --check
```

Create or choose an experiment project:

```text
my_experiment/
├── PROJECT_BRIEF.md
└── config.yaml          # optional
```

Minimal `PROJECT_BRIEF.md`:

```markdown
# Goal
Train a CIFAR-100 classifier to reach 80%+ top-1 accuracy.

# Codebase
Create or modify PyTorch training code in this project.

# Constraints
- Use GPU 0 only
- Always dry-run before long training
- Report validation accuracy after each run

# Decision Rules
- If accuracy is below 75%, improve optimization.
- If accuracy is 75-80%, try augmentation.
- If accuracy reaches 80%, stop and write a report.
```

Start from Claude Code:

```bash
/auto-research --project /path/to/my_experiment --gpu 0
```

Or start from the Python entrypoint:

```bash
python -m auto_researcher.runner --project /path/to/my_experiment --gpu 0
```

Send a one-cycle directive:

```bash
python -m auto_researcher.runner \
  --project /path/to/my_experiment \
  --directive "Search recent papers about cosine warmup before the next run"
```

## Architecture

<p align="center">
  <img src="assets/readme/architecture.png" alt="Auto Researcher architecture" width="900"/>
</p>

Auto Researcher uses a leader-worker loop with deterministic routing guards:

| Stage | What Happens |
|-------|--------------|
| `Leader / Think` | Reads project state and proposes the next action |
| `Strategy Router` | Forces idea/code handoffs when configured |
| `Idea` | Searches papers and writes actionable hypotheses |
| `Code Modify` | Edits code/configs, often via Codex CLI |
| `Framework Launch` | Runs dry-run and `launch_experiment` itself |
| `Monitor` | Checks PID, logs, and GPU status with zero LLM calls |
| `Reflect` | Parses metrics, updates memory, ledger, and journals |

The monitor phase is intentionally cheap: no LLM call is made while training is running.

## Recommended Hybrid Setup

Use Codex CLI where it is strongest: planning, reflection, and code modification. Keep actual training launch inside Auto Researcher.

```yaml
agent:
  provider: "openai"
  model: "gpt-5.4"
  api_key_env: "OPENAI_API_KEY"

  leader_provider: "codex_cli"
  reflect_provider: "codex_cli"
  code_modify_provider: "codex_cli"
  code_launch_provider: "builtin"
  idea_provider: "openai"
  writing_provider: "openai"

strategy:
  enabled: true
  require_initial_ideation: true
  stagnation_cycles_before_idea: 3
  idea_to_code_handoff: true
  require_dry_run: true
  dry_run_timeout: 300
```

Why split `code_modify_provider` and `code_launch_provider`?

- `codex_cli` may use its own agentic tool loop.
- That is useful for editing code.
- It is risky for launching training because it can bypass framework PID/log tracking.
- `code_launch_provider: "builtin"` keeps dry-run and training launch authoritative.

## Configuration

Default config lives in [`config.yaml`](config.yaml). The most important sections are:

| Section | Purpose |
|---------|---------|
| `agent` | Cloud provider, model, role-specific overrides |
| `strategy` | Deterministic idea/code routing rules |
| `execution` | Local, SSH, or Slurm execution backend |
| `ledger` | Append-only experiment history |
| `journal` | Durable `DEAD_ENDS.md` and `INSIGHTS.md` |
| `monitor` | Zero-LLM polling behavior |
| `notes` | Dashboard and daily progress note export |

Cloud provider examples:

```yaml
agent:
  provider: "openai"
  model: "gpt-5.4"
  api_key_env: "OPENAI_API_KEY"
```

```yaml
agent:
  provider: "deepseek"
  model: "deepseek-chat"
```

Supported provider paths include:

- `openai`
- `anthropic`
- `claude_cli`
- `codex_cli`
- OpenAI-compatible presets: `deepseek`, `qwen`, `dashscope`, `kimi`, `moonshot`, `glm`, `zhipu`

No local LLM server is required.

## Skills

Install Claude Code slash commands and Codex local skills:

```bash
python install.py
```

Available skills:

| Claude Code | Codex | Purpose |
|-------------|-------|---------|
| `/auto-research` | `$auto-research` | Launch or resume the autonomous loop |
| `/experiment-status` | `$experiment-status` | Inspect state, PID, logs, GPU, ledger |
| `/gpu-monitor` | `$gpu-monitor` | Check GPU availability |
| `/daily-papers` | `$daily-papers` | Get arXiv recommendations |
| `/paper-analyze` | `$paper-analyze` | Analyze a paper |
| `/conf-search` | `$conf-search` | Search conference papers |
| `/progress-report` | `$progress-report` | Summarize recent experiments |
| `/notes-sync` | `$notes-sync` | Refresh dashboard and daily notes |

Uninstall:

```bash
python install.py --uninstall
```

## Project State

Each experiment project keeps state under `workspace/`:

```text
workspace/
├── MEMORY_LOG.md
├── experiments.jsonl
├── DEAD_ENDS.md
├── INSIGHTS.md
├── state.json
├── HUMAN_DIRECTIVE.md        # optional, consumed next cycle
└── progress_tracking/        # local notes fallback
```

These files are part of the control surface. They make the loop inspectable and interruptible.

## Execution Backends

Local execution:

```yaml
execution:
  mode: "local"
```

SSH execution:

```yaml
execution:
  mode: "ssh"
  ssh_host: "user@server"
  remote_workspace: "/home/user/project/workspace"
```

Slurm execution:

```yaml
execution:
  mode: "slurm"
  ssh_host: "user@login-node"
  remote_workspace: "/shared/project/workspace"
  slurm_partition: "gpu"
  slurm_time: "24:00:00"
  slurm_gpus_per_job: 1
```

In all modes, the framework records the authoritative PID or job id and log path.

## Development

Run the full test suite:

```bash
python -m unittest discover tests
python -m py_compile auto_researcher/*.py auto_researcher/gpu/*.py install.py
python -m auto_researcher.runner --check
```

Current validation target:

- unit tests pass without a GPU
- skill installer install/uninstall is covered
- tool path safety is tested
- local, SSH, and Slurm execution logic is tested with mocks

## Repository Layout

```text
auto_researcher/
├── auto_researcher/
│   ├── runner.py
│   ├── dispatch.py
│   ├── tool_registry.py
│   ├── execution.py
│   ├── monitor.py
│   ├── memory.py
│   ├── ledger.py
│   ├── journal.py
│   ├── safety.py
│   ├── notes.py
│   └── gpu/
├── prompts/
│   ├── leader.md
│   ├── idea.md
│   ├── code.md
│   └── writing.md
├── skills/
│   ├── auto-research/
│   ├── experiment-status/
│   ├── gpu-monitor/
│   ├── daily-papers/
│   ├── paper-analyze/
│   ├── conf-search/
│   ├── progress-report/
│   └── notes-sync/
├── tests/
├── assets/readme/
├── config.yaml
└── install.py
```

## Research Integrity

Auto Researcher is an experiment operator, not a replacement researcher. Use it to run repetitive cycles, gather evidence, and keep records. Keep the research question, interpretation, and final scientific judgment with the human.

