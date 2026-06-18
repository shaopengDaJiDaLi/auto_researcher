# Auto Researcher

<p align="center">
  <img src="assets/readme/hero.png" alt="Auto Researcher hero" width="900"/>
</p>

<p align="center">
  <strong>A Codex CLI-driven controller for long-running deep learning experiments.</strong>
</p>

<p align="center">
  <a href="README.md">English</a> |
  <a href="docs/README_CN.md">中文</a>
</p>

<p align="center">
  <a href="#install">Install</a> |
  <a href="#quickstart">Quickstart</a> |
  <a href="#configuration">Configuration</a> |
  <a href="#how-it-works">How It Works</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/Codex%20CLI-required-111827.svg" alt="Codex CLI required"/>
  <img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License"/>
</p>

---

## What This Is

Auto Researcher is not a standalone model and not just a prompt pack. It is a controller around **Codex CLI** for autonomous experiment operations:

1. Read a research brief and current experiment state.
2. Ask Codex CLI to inspect and modify the codebase.
3. Run a required dry-run.
4. Launch training through Auto Researcher, not directly through Codex.
5. Monitor PID, logs, and GPU status with zero LLM calls.
6. Reflect on results, update memory and the experiment ledger, then continue.

The important boundary is deliberate: **Codex writes code; Auto Researcher launches and monitors training.** That keeps long-running jobs traceable through recorded PID/log paths instead of leaving them hidden inside an agent session.

## Install

### 1. Install Codex CLI

Codex CLI is the required coding agent for the recommended workflow.

On macOS or Linux:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

Alternative installs:

```bash
npm install -g @openai/codex
brew install --cask codex
```

Then sign in. Running `codex` opens the normal interactive flow; current CLI versions also support `codex login`:

```bash
codex login
```

Verify:

```bash
codex --version
```

### 2. Install Auto Researcher

```bash
git clone https://github.com/shaopengDaJiDaLi/auto_researcher.git
cd auto_researcher

conda create -n autoR python=3.11 -y
conda activate autoR
pip install -r requirements.txt

python install.py
python -m auto_researcher.runner --check
```

If you do not use conda, use a local virtual environment instead:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`python install.py` installs the local Codex skills, including `$auto-research`.

## Quickstart

Create an experiment project:

```bash
mkdir -p ~/my_experiment
cd ~/my_experiment
```

Write `PROJECT_BRIEF.md`:

```markdown
# Goal
Train a CIFAR-100 classifier to reach 80%+ top-1 accuracy.

# Codebase
Create or modify PyTorch training code in this project.

# Constraints
- Use GPU 0 only
- Always dry-run before long training
- Write logs under ./logs/
- Report validation accuracy after each run

# Decision Rules
- If accuracy is below 75%, improve optimization.
- If accuracy is 75-80%, try augmentation.
- If accuracy reaches 80%, stop and write a report.
```

Add an optional per-project config when this experiment needs settings different from the default [`config.yaml`](config.yaml). Here, "project" means the experiment/code directory you pass to `--project`, such as `~/my_experiment`; you do not need to create this file for every run.

```yaml
# ~/my_experiment/config.yaml
# This file belongs to one experiment project directory.
# Omit it to use Auto Researcher's default config.
# Add it when a project needs its own provider, GPU backend, dry-run policy,
# SSH/Slurm execution settings, or role-specific overrides.
agent:
  provider: "codex_cli"
  model: "gpt-5.4"

  leader_provider: "codex_cli"
  reflect_provider: "codex_cli"
  code_modify_provider: "codex_cli"
  code_launch_provider: "builtin"

strategy:
  enabled: true
  require_dry_run: true
  dry_run_timeout: 300

execution:
  mode: "local"
```

There are three common ways to start Auto Researcher:

1. **Method 1: Codex skill** — recommended for normal use inside Codex.
2. **Method 2: Python entrypoint** — useful for servers, tmux, SSH sessions, and scripts.
3. **Method 3: Limited or directed run** — useful when testing, debugging, or giving one explicit instruction.

### Method 1: Start From Codex

Use this after `python install.py` has installed the `$auto-research` skill:

```text
$auto-research --project ~/my_experiment --gpu 0
```

### Method 2: Start From Python

Use this when you want a plain shell command, for example inside `tmux` or on a remote server:

```bash
cd /path/to/auto_researcher
python -m auto_researcher.runner --project ~/my_experiment --gpu 0
```

### Method 3: Limited Or Directed Run

Run only a few cycles while testing:

```bash
python -m auto_researcher.runner \
  --project ~/my_experiment \
  --gpu 0 \
  --max-cycles 2
```

Send one explicit directive for the next cycle:

```bash
python -m auto_researcher.runner \
  --project ~/my_experiment \
  --gpu 0 \
  --directive "Try cosine warmup and compare with the current best run"
```

## Configuration

Default configuration is in [`config.yaml`](config.yaml). For this project, the recommended setup is Codex CLI for reasoning and code edits, with built-in launch control:

```yaml
agent:
  provider: "codex_cli"
  model: "gpt-5.4"

  leader_provider: "codex_cli"
  reflect_provider: "codex_cli"
  code_modify_provider: "codex_cli"
  code_launch_provider: "builtin"
```

Why `code_launch_provider: "builtin"` matters:

- Codex CLI is good at reading and changing code.
- Training launch must stay controlled by Auto Researcher.
- Auto Researcher records the authoritative PID/job id and log file.
- Monitoring then reads process state, GPU state, and log tails without spending LLM calls.

Optional cloud API roles are still supported. Use them when you want literature search or writing roles to run through an OpenAI-compatible API:

```yaml
agent:
  provider: "codex_cli"
  model: "gpt-5.4"

  leader_provider: "codex_cli"
  reflect_provider: "codex_cli"
  code_modify_provider: "codex_cli"
  code_launch_provider: "builtin"

  idea_provider: "openai"
  idea_model: "gpt-5.4"
  idea_api_key_env: "OPENAI_API_KEY"
  writing_provider: "openai"
  writing_model: "gpt-5.4"
  writing_api_key_env: "OPENAI_API_KEY"
```

Supported provider paths include:

| Provider | Use case |
|----------|----------|
| `codex_cli` | Recommended code editing and controller reasoning |
| `openai` | OpenAI-compatible API calls |
| `anthropic` | Anthropic-compatible API calls |
| `claude_cli` | Optional Claude Code CLI path |
| `deepseek`, `qwen`, `dashscope`, `kimi`, `moonshot`, `glm`, `zhipu` | OpenAI-compatible presets |

## How It Works

<p align="center">
  <img src="assets/readme/architecture.png" alt="Auto Researcher architecture" width="900"/>
</p>

| Stage | Responsibility |
|-------|----------------|
| Think | Read `PROJECT_BRIEF.md`, memory, ledger, state, and directives |
| Route | Choose `idea`, `code`, or `writing` for the next cycle |
| Code Modify | Codex CLI edits code/configs and returns a launch handoff |
| Dry Run | Auto Researcher runs the dry-run command |
| Launch | Auto Researcher launches training and records PID/log path |
| Monitor | Poll process, GPU, and log file with zero LLM calls |
| Reflect | Parse metrics, update memory, ledger, insights, and dead ends |

For code work, Codex should return a handoff like:

```json
{
  "status": "ready_to_launch",
  "changed_files": ["train.py", "configs/exp.yaml"],
  "dry_run_command": "python train.py --config configs/exp.yaml --max_steps 2",
  "launch_command": "python train.py --config configs/exp.yaml",
  "log_file": "logs/exp_001.log",
  "expected_duration": "8 hours"
}
```

Auto Researcher uses that handoff to run the dry-run and launch command itself.

## Project State

Each experiment project keeps durable state under `workspace/`:

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

To redirect the next cycle:

```bash
echo "Try cosine warmup and compare against the last best run" > workspace/HUMAN_DIRECTIVE.md
```

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

In every backend, Auto Researcher owns the job id or PID and the log path.

## Skills

`python install.py` installs Codex local skills:

| Codex skill | Purpose |
|-------------|---------|
| `$auto-research` | Launch or resume the autonomous loop |
| `$experiment-status` | Inspect state, PID, logs, GPU, ledger |
| `$gpu-monitor` | Check GPU availability |
| `$daily-papers` | Get arXiv recommendations |
| `$paper-analyze` | Analyze a paper |
| `$conf-search` | Search conference papers |
| `$progress-report` | Summarize recent experiments |
| `$notes-sync` | Refresh dashboard and daily notes |

Uninstall:

```bash
python install.py --uninstall
```

## Development

Run checks:

```bash
python -m unittest discover tests
python -m py_compile auto_researcher/*.py auto_researcher/gpu/*.py install.py
python -m auto_researcher.runner --check
```

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
├── skills/
├── tests/
├── assets/readme/
├── config.yaml
└── install.py
```

## Research Integrity

Auto Researcher is an experiment operator. It can run repetitive cycles, collect evidence, and keep records, but the research question, interpretation, and scientific responsibility stay with the human researcher.
