# AI Guide — Auto Researcher

> **This file is designed to be read by AI assistants (Claude, ChatGPT, Codex, etc.).**
> When a user pastes this file or asks you to help them set up Auto Researcher,
> follow the instructions below to guide them step by step.

---

## What Is This?

Auto Researcher is a framework that lets an AI agent autonomously run deep learning experiments 24/7. The agent:
1. **Thinks** — analyzes results, plans the next experiment
2. **Executes** — modifies code, dry-runs, launches GPU training
3. **Monitors** — watches training at ZERO LLM cost (only process checks + log reads)
4. **Reflects** — parses results, compares with baseline, decides next step
5. **Repeats** — 24/7 without human intervention

The killer feature: during training (which is 90%+ of the time), the agent makes ZERO API calls. A 24-hour cycle costs ~$0.08.

---

## Your Job as AI Assistant

When a user asks for help with this project, follow this decision tree:

```
User wants to...
├── Install it → Go to [SETUP GUIDE]
├── Create a project → Go to [PROJECT CREATION]
├── Launch the agent → Go to [LAUNCH GUIDE]
├── Check status → Go to [STATUS CHECK]
├── Intervene/redirect → Go to [INTERVENTION]
├── Use on phone → Go to [MOBILE SETUP]
├── Understand how it works → Go to [ARCHITECTURE EXPLANATION]
└── Debug an issue → Go to [TROUBLESHOOTING]
```

---

## SETUP GUIDE

### Step 1: Check Prerequisites

Run these commands and report results to the user:

```bash
python3 --version          # Need 3.10+
nvidia-smi                 # Need at least 1 GPU
echo $ANTHROPIC_API_KEY    # Anthropic-compatible key, if using provider=anthropic
echo $OPENAI_API_KEY       # OpenAI-compatible key, if using provider=openai
```

If Python < 3.10: suggest `conda create -n dra python=3.11 -y && conda activate dra`

If no GPU: this framework requires a GPU for training. Suggest cloud GPU (Lambda Labs, RunPod, Vast.ai).

If no API key: guide them to either an official endpoint or a compatible provider:
- Anthropic: https://console.anthropic.com/ → API Keys → Create Key
- OpenAI: https://platform.openai.com/api-keys → Create new secret key
- DeepSeek (`provider: deepseek`): create `DEEPSEEK_API_KEY`
- Qwen / DashScope (`provider: qwen`): create `DASHSCOPE_API_KEY`
- Kimi / Moonshot (`provider: kimi`): create `MOONSHOT_API_KEY`
- GLM / BigModel (`provider: glm`): create `ZHIPUAI_API_KEY`
- MiniMax: create `MINIMAX_API_KEY`

Then set it:
```bash
# Pick ONE:
export ANTHROPIC_API_KEY="sk-ant-xxxxx"   # For Claude
export OPENAI_API_KEY="sk-xxxxx"          # For Codex/GPT

# Make permanent:
echo 'export ANTHROPIC_API_KEY="sk-ant-xxxxx"' >> ~/.bashrc
source ~/.bashrc
```

### Step 2: Install

```bash
# If not already cloned:
git clone https://github.com/shaopengDaJiDaLi/auto_researcher.git
cd auto_researcher

# Install dependencies
pip install -r requirements.txt

# Install Claude slash commands + Codex local skills
python install.py

# Verify
python -m auto_researcher.runner --check
```

**Expected output:**
```
    ✓ Claude /auto-research
    ✓ Claude /experiment-status
    ✓ Claude /gpu-monitor
    ✓ Claude /daily-papers
    ✓ Claude /paper-analyze
    ✓ Claude /conf-search
    ✓ Claude /progress-report
    ✓ Claude /notes-sync
    ✓ Codex $auto-research
    ...
  Done! 8 Claude commands and 8 Codex skills installed.
```

### Step 3: Choose Your LLM Provider

Ask the user two questions:

1. **Which vendor?** — Anthropic (Claude) or OpenAI (Codex/GPT)?
2. **API key or subscription?** — an existing Claude / ChatGPT subscription is
   usually *much* cheaper than per-token API billing for 24/7 agent use.

| Provider value | Vendor | Billing | Auth |
|----------------|--------|---------|------|
| `anthropic` | Anthropic-compatible | Per-token API | `ANTHROPIC_API_KEY` or custom env |
| `openai` | OpenAI-compatible | Per-token API | `OPENAI_API_KEY` or custom env |
| `claude_cli` | Anthropic | **Flat-rate subscription** | `claude` CLI installed + logged in |
| `codex_cli` | OpenAI | **Flat-rate subscription** | `codex` CLI installed + logged in |
| `deepseek` / `qwen` / `kimi` / `glm` | Domestic OpenAI-compatible preset | Per-token API | `DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY` / `MOONSHOT_API_KEY` / `ZHIPUAI_API_KEY` |

**Domestic LLM APIs (replace a Claude/Codex subscription with a Chinese API):** set
`provider` to a one-word preset and `model` to that vendor's model id — the preset
auto-fills the OpenAI-compatible `base_url` and the default key env. Aliases:
`qwen`=`dashscope`, `kimi`=`moonshot`, `glm`=`zhipu`. Tell the user to export the
matching key, e.g. `export DEEPSEEK_API_KEY=...`, then:

```yaml
agent:
  provider: "deepseek"     # or qwen / kimi / glm
  model: "deepseek-chat"   # vendor's model id (e.g. qwen-max, kimi-k2, glm-4.6)
```

`base_url` / `api_key_env` remain overridable for other cloud API endpoints.

Model tiers:

| Provider | Fast Model | Strong Model |
|----------|-----------|-------------|
| Anthropic (API or CLI) | claude-sonnet-4-6 | claude-opus-4-6 |
| OpenAI (API or CLI) | codex-5.3 | gpt-5.4 |

Default is `anthropic`. To switch, edit `config.yaml`:
```yaml
agent:
  provider: "openai"            # or "anthropic" / "claude_cli" / "codex_cli"
  model: "codex-5.3"            # or claude-sonnet-4-6 / claude-opus-4-6 / gpt-5.4
  base_url: ""                  # optional cloud API endpoint override
  api_key_env: ""               # optional custom key env var
  auth_token_env: ""            # optional custom bearer token env var
```

For Codex CLI, prefer hybrid mode instead of making every worker use
`codex_cli`:

```yaml
agent:
  provider: "openai"
  model: "gpt-5.4"
  leader_provider: "codex_cli"
  reflect_provider: "codex_cli"
  code_modify_provider: "codex_cli"
  code_launch_provider: "builtin"
  idea_provider: "openai"
  writing_provider: "openai"

strategy:
  require_initial_ideation: true
  stagnation_cycles_before_idea: 3
  idea_to_code_handoff: true
```

In this mode Codex plans and edits code, but the framework still runs dry-run
and `launch_experiment`, preserving PID/log handoff for monitoring.

Compatible API examples — for the common domestic vendors prefer the one-word
preset above (`deepseek` / `qwen` / `kimi` / `glm`). The manual `provider: "openai"`
+ `base_url` form below is for any *other* OpenAI-compatible cloud vendor
(illustrative — these endpoint/model combinations are not live-smoke-tested here):

```yaml
# Qwen / DashScope
agent:
  provider: "openai"
  model: "qwen-plus"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  api_key_env: "DASHSCOPE_API_KEY"

# GLM / BigModel
agent:
  provider: "openai"
  model: "glm-4.5"
  base_url: "https://open.bigmodel.cn/api/paas/v4"
  api_key_env: "ZHIPUAI_API_KEY"

# MiniMax via OpenAI-compatible endpoint
agent:
  provider: "openai"
  model: "MiniMax-M1"
  base_url: "https://api.minimaxi.com/v1"
  api_key_env: "MINIMAX_API_KEY"
```

Optional remote execution modes (`execution.mode`):

```yaml
# SSH — run on one remote host
execution:
  mode: "ssh"
  ssh_host: "user@server"
  remote_workspace: "/home/user/my_project/workspace"
  remote_python: "python3"
  ssh_args: []                  # optional, e.g. ["-p", "2222"]

# Slurm — submit training to a Slurm cluster via its login node
execution:
  mode: "slurm"
  ssh_host: "user@login-node"
  remote_workspace: "/nfs/home/user/my_project/workspace"   # shared NFS
  slurm_partition: "gpu"        # required
  slurm_time: "24:00:00"        # required, --time wall limit
  slurm_gpus_per_job: 1         # -> --gres=gpu:1
  slurm_setup: "module load cuda/12.4"   # optional, prepended to the job
```

In SSH/Slurm mode, the controller state still stays local:
- `PROJECT_BRIEF.md`
- `workspace/MEMORY_LOG.md`
- `workspace/state.json`
- `workspace/HUMAN_DIRECTIVE.md`
- local progress / notes exports

The remote host handles code edits, shell commands, training, log reads, and
status checks. **Slurm specifics:** training is submitted with `sbatch --parsable`
over one transient SSH call that exits immediately — nothing is left running on the
login node. Liveness comes from `sacct` (Slurm enforces `--time`), GPUs are assigned
via `--gres`, and file ops run on the login node (shared NFS). See `config.yaml` for
the full set of `slurm_*` keys (`slurm_qos`, `slurm_account`, `slurm_extra_sbatch`, …).

**When to pick subscription (`claude_cli` / `codex_cli`):**
- Running multiple agents in parallel (one subscription can power them all)
- Heavy Think / Reflect usage where API tokens would add up
- You already pay for a Claude or ChatGPT subscription and want to amortize it

**Trade-off:** CLI mode has no native prompt caching and no structured tool-use
protocol — the CLI is used as a text-in / text-out oracle. For this framework
that is fine, because the Leader / Worker loop already sends one flat prompt per
dispatch. For workloads that need fine-grained tool calls, stick to the API
providers.

---

## PROJECT CREATION

### Ask the User These Questions:

1. **What's your research goal?** (e.g., "Train a ViT on CIFAR-100 to 85% accuracy")
2. **Do you already have training code?** (Yes → point to it / No → agent will create it)
3. **Where is your data?** (path or "auto-download")
4. **Which GPU(s) can you use?** (run `nvidia-smi` to check)
5. **Any constraints?** (max epochs, batch size, etc.)

### Create the Project Directory:

```bash
mkdir ~/PROJECT_NAME
cd ~/PROJECT_NAME
```

### Write PROJECT_BRIEF.md:

This is THE most important file. Write it based on the user's answers:

```markdown
# Goal
[User's research goal with specific metric and target value]

# Codebase
[If existing code: list files and paths]
[If no code: "Agent should create PyTorch training code from scratch"]
- Data: [path or "auto-download via torchvision"]
- Checkpoints: ./checkpoints/
- Logs: ./logs/

# What to Try
[Decision tree based on user's domain knowledge]
- First try: [baseline config]
- If [metric] < [threshold1]: try [approach A]
- If [metric] between [threshold1] and [threshold2]: try [approach B]
- If [metric] > [target]: goal reached, generate report

# Constraints
- GPU: [which GPU(s)]
- Max epochs per run: [number]
- Batch size: [number]
- [Any other constraints]

# Current Status
[No experiments yet / Previous best: X]
```

### Key Tips to Tell the User:

- **Be specific about the goal** — "accuracy > 80%" not "improve accuracy"
- **Give a decision tree** — the agent needs to know what to do in each situation
- **Keep it under 3000 characters** — this is the Tier 1 memory cap
- **Think of it as instructing a capable but new PhD student**

---

## LAUNCH GUIDE

### Option A: Claude Code / Codex CLI

```
/auto-research --project ~/PROJECT_NAME --gpu 0
```

### Option B: Python Direct

```bash
python -m auto_researcher.runner \
  --project ~/PROJECT_NAME \
  --gpu 0 \
  --max-cycles 5    # Optional: limit cycles (remove for unlimited)
```

### What to Tell the User:

"The agent is now running. Here's what will happen:
1. It reads your PROJECT_BRIEF.md
2. It plans the first experiment
3. It writes/modifies code
4. It does a dry-run (2 steps) to catch errors
5. It launches real training
6. During training: ZERO API cost — it just checks if the process is alive
7. When training finishes, it analyzes results and plans the next experiment
8. This repeats until you stop it or the goal is reached

You can close this terminal — the training continues via nohup.
Check back anytime with /experiment-status."

---

## STATUS CHECK

```bash
# In Claude Code / Codex:
/experiment-status --project ~/PROJECT_NAME

# Check GPUs:
/gpu-monitor

# Or manually:
cat ~/PROJECT_NAME/workspace/MEMORY_LOG.md    # See results and decisions
cat ~/PROJECT_NAME/workspace/.cycle_counter   # See how many cycles completed
nvidia-smi                                     # See GPU usage
```

If `execution.mode=ssh`, those manual checks split:

```bash
# Controller state still local:
cat ~/PROJECT_NAME/workspace/MEMORY_LOG.md
cat ~/PROJECT_NAME/workspace/.cycle_counter

# Training logs / GPU state live on the remote host:
ssh user@server 'tail -50 /home/user/my_project/workspace/logs/exp001.log'
ssh user@server nvidia-smi
```

If `execution.mode=slurm`, the workspace/logs live on shared NFS and job state
comes from Slurm (the login node has no usable `nvidia-smi`):

```bash
ssh user@login-node 'tail -50 /nfs/home/user/my_project/workspace/logs/exp001.log'
ssh user@login-node 'squeue --me'          # your queued/running jobs
ssh user@login-node 'sacct -X --format=JobID,State,Elapsed -S today'   # outcomes
```

For persistent progress notes:

```yaml
notes:
  enabled: true
  vault_path: "~/Documents/MynotesVault"   # Optional
  project_subdir: "AutoResearcher/{project_name}"
  auto_append_daily: true
```

- If `vault_path` is set, write `Dashboard.md` and daily Markdown notes into that notes vault.
- If `vault_path` is empty, fall back to project-local text files under `workspace/progress_tracking/`.
- Manual refresh:

```bash
/notes-sync --project ~/PROJECT_NAME
# or
python -m auto_researcher.notes --project ~/PROJECT_NAME
```

---

## INTERVENTION

The user wants to change the agent's direction. Three methods:

### Method 1: Directive File (Recommended)
```bash
echo "YOUR INSTRUCTION HERE" > ~/PROJECT_NAME/workspace/HUMAN_DIRECTIVE.md
```
The agent reads this at the start of the next cycle with HIGHEST priority, then auto-archives it.

Examples:
- `"Stop trying ResNet. Switch to ViT-B/16 with lr=1e-3"`
- `"The last 3 experiments all used lr=0.1. Try smaller: 1e-3, 1e-4, 1e-5"`
- `"Goal reached! Generate a final report with all results."`

### Method 2: Command-Line
```bash
python -m auto_researcher.runner --project ~/PROJECT_NAME --directive "Try label smoothing 0.1"
```

### Method 3: Edit Memory
```bash
vim ~/PROJECT_NAME/workspace/MEMORY_LOG.md
```
This is for permanent changes. The agent reads this every cycle.

---

## MOBILE SETUP

For checking experiments from phone:

```bash
# Install Happy Coder CLI
npm install -g happy-coder

# Start session through Happy
happy

# Inside: launch experiment
/auto-research --project ~/PROJECT_NAME --gpu 0
```

Then install the Happy Coder app:
- iOS: https://apps.apple.com/us/app/happy-codex-claude-code-app/id6748571505
- Android: https://play.google.com/store/apps/details?id=com.ex3ndr.happy

Scan QR code to pair. Now the user gets push notifications and can send directives from their phone.

---

## ARCHITECTURE EXPLANATION

Use this when the user asks "how does it work?":

### The Loop
```
THINK (LLM, ~$0.05) → EXECUTE (LLM→training) → MONITOR ($0.00) → REFLECT (LLM, ~$0.03) → repeat
```

### Why It's Cheap
During training (90%+ of time), the agent does NOT call the LLM. It only does:
- backend liveness check — is the job alive? (zero cost)
- backend `nvidia-smi` — is GPU active? (zero cost)
- backend `tail -50 logfile` — latest metrics (zero cost)

In local mode the backend is your current machine. In SSH mode it is one configured
remote host. In **Slurm** mode liveness comes from a transient `sacct` query (not a
PID), and there is no persistent process on the login node.

**Truthful experiment outcomes:** when a job finishes, the agent records whether it
actually **completed** or **failed** (e.g. Slurm `FAILED` / `TIMEOUT` / `CANCELLED`)
rather than assuming success — the outcome flows into `state.json`, the experiment
ledger, and the REFLECT context, so the agent reacts to real failures instead of
reasoning over a crashed run's partial log. (pid-only `local`/`ssh` backends report
the outcome as indeterminate and keep prior behavior.)

### Memory System
- Tier 1: `PROJECT_BRIEF.md` — frozen, human-written, max 3000 chars
- Tier 2: `MEMORY_LOG.md` — rolling, auto-compacted, max 2000 chars
- Total: ~5000 chars CONSTANT, whether running 1 day or 6 months

### Agent Architecture
- **Leader**: decides what to do (3 tools)
- **Idea**: literature search & hypotheses — `search_papers`, `search_arxiv`, `get_paper` (reference/citation snowballing), plus read/write (5 tools)
- **Code**: writes code & launches experiments — adds `list_tree` (recursive repo map) and `search_code` (regex grep) for codebase comprehension (7 tools)
- **Writing**: generates reports — read/write/list plus `search_code` (4 tools)
- Only 1 worker active at a time, others cost $0

### Tool-Use Protocol (provider-agnostic)

Workers do not use each provider's native SDK tool-use protocol. Instead the
framework injects a plain-text schema into the system prompt and the worker
emits tool calls as `<tool_call>{...}</tool_call>` blocks. The dispatcher
parses the blocks, runs each through `ResearchToolRegistry.execute_tool`, and feeds
results back as `<tool_result name="...">...</tool_result>` in the next user
turn. The loop runs until the worker produces a response with no tool calls
(the final answer) or `max_turns` is reached.

Why this design:

- **One protocol, four providers** — the Anthropic and OpenAI SDK paths use
  the same text protocol as `claude_cli` and `codex_cli`. No per-provider
  branching in the execution loop.
- **Authoritative PID / log_file** — the EXECUTE → MONITOR handoff reads
  `pid` and `log_file` directly from the `launch_experiment` tool's JSON
  result, not from regex-scraping the model's prose.
- **Provider-lock-down** — for `claude_cli` the framework passes
  `--tools ""` so the CLI cannot bypass the protocol with its own built-in
  tools. `codex_cli` has no equivalent flag and will silently ignore the
  protocol; a runtime warning is emitted when it is used as a worker, and
  users should pick one of the other three providers for worker dispatches.
- **Fence stripping** — tool-call blocks inside triple-backtick code fences
  are ignored, so a model's illustrative example in its prose is never
  accidentally executed.

### Safety
- Mandatory dry-run before every real training
- Protected files can't be overwritten
- Anti-burn protection (backs off if stuck in empty loops)
- Human can intervene anytime via directive file

---

## TROUBLESHOOTING

### "No GPU found"
```bash
nvidia-smi  # Check if CUDA drivers are installed
```
If not: install NVIDIA drivers for your GPU.

### "anthropic/openai package not found"
```bash
pip install anthropic openai
```

### "API key not set"
```bash
export ANTHROPIC_API_KEY="your-key-here"
# OR
export OPENAI_API_KEY="your-key-here"
# OR a domestic-preset key matching agent.provider:
export DEEPSEEK_API_KEY="..."   # provider: deepseek
export DASHSCOPE_API_KEY="..."  # provider: qwen
export MOONSHOT_API_KEY="..."   # provider: kimi
export ZHIPUAI_API_KEY="..."    # provider: glm
```

### "Dry-run failed"
This is working as intended! The dry-run caught an error before wasting GPU hours. Check the error message and fix the code, or let the agent fix it in the next cycle.

### "Agent keeps trying the same thing"
Drop a directive:
```bash
echo "You've tried X three times. Try something completely different: Y" \
  > workspace/HUMAN_DIRECTIVE.md
```

### "Training crashed"
The agent automatically detects when a job ends, reads the error log, and tries to fix the issue. It records the real outcome — `completed` vs `failed` — so a crash/timeout is not mislabelled as success (on Slurm the outcome comes from the `sacct` terminal state). If it keeps crashing, intervene with a directive.

### "Memory is full / context too long"
This shouldn't happen — memory is capped at 5K chars. If it does, check:
```bash
wc -c PROJECT_BRIEF.md           # Should be < 3000
wc -c workspace/MEMORY_LOG.md    # Should be < 2000
```

### "Want to start fresh"
```bash
rm -rf workspace/                 # Delete all agent state
# PROJECT_BRIEF.md is preserved
python -m auto_researcher.runner --project .   # Restart from scratch
```

---

## QUICK REFERENCE

| Command | What It Does |
|---------|-------------|
| `/auto-research --project PATH --gpu 0` | Start 24/7 experiment loop |
| `/experiment-status` | Check progress |
| `/gpu-monitor` | GPU status |
| `/daily-papers` | Paper recommendations |
| `/paper-analyze ARXIV_ID` | Deep paper analysis |
| `/conf-search --venue CVPR2025 --query "xxx"` | Conference search |
| `/progress-report` | Generate report |
| `echo "instruction" > workspace/HUMAN_DIRECTIVE.md` | Redirect agent |
| `python install.py --uninstall` | Remove all skills |

---

## IMPORTANT CONTEXT FOR AI ASSISTANTS

- This framework works with ANY training framework (PyTorch, TensorFlow, JAX, etc.)
- The agent can create code from scratch OR modify existing code
- It's not just hyperparameter tuning — it can change architectures, loss functions, augmentation strategies
- The agent is NOT a chatbot — it's an autonomous loop that runs independently
- Cost is ~$0.08/day, not $50+/day, because of zero-cost monitoring
- If the user is confused, start with: "Let's create a simple project first and watch the agent work"
