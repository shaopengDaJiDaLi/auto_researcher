"""
Auto Researcher Core Loop

The autonomous THINK → EXECUTE → REFLECT cycle that drives experiments 24/7.
"""

import os
import sys
import time
import json
import re
import signal
import argparse
import logging
from pathlib import Path
from typing import Optional

from .memory import MemoryManager
from .monitor import ExperimentMonitor
from .dispatch import RoleDispatcher
from .execution import build_execution_backend
from .notes import NotesExporter
from .tool_registry import ResearchToolRegistry
from .ledger import ExperimentLedger, detect_stagnation, check_phase_gate
from .journal import ResearchJournal
from . import safety

logger = logging.getLogger("auto_researcher")


class AutoResearcher:
    """Main autonomous research loop.

    Implements the THINK → EXECUTE → REFLECT cycle:
    - THINK: Analyze state, form hypothesis, plan experiment
    - EXECUTE: Dispatch code agent to implement and run experiment
    - REFLECT: Evaluate results, update memory, decide next action
    """

    def __init__(self, config: dict, project_dir: str):
        self.config = config
        self.project_dir = Path(project_dir).resolve()
        self.workspace = self.project_dir / config.get("project", {}).get("workspace", "workspace")
        self.workspace.mkdir(exist_ok=True)
        self.state_path = self.workspace / "state.json"
        self.execution_backend = build_execution_backend(config=config, controller_workspace=self.workspace)
        self.execution_backend.validate()

        # Core components
        self.memory = MemoryManager(
            project_dir=self.project_dir,
            brief_max=config.get("memory", {}).get("brief_max_chars", 3000),
            log_max=config.get("memory", {}).get("log_max_chars", 2000),
            milestone_max=config.get("memory", {}).get("milestone_max_chars", 1200),
            max_recent=config.get("memory", {}).get("max_recent_entries", 15),
        )
        self.monitor = ExperimentMonitor(
            poll_interval=config.get("monitor", {}).get("poll_interval", 900),
            zero_llm=config.get("monitor", {}).get("zero_llm", True),
            backend=self.execution_backend,
        )
        agent_config = config.get("agent", {}) or {}
        self.dispatchers = self._build_dispatchers(agent_config)
        self.dispatcher = self.dispatchers["leader"]
        self.tools = ResearchToolRegistry(self.execution_backend)
        self.notes = NotesExporter(
            config=config,
            project_dir=self.project_dir,
            backend=self.execution_backend,
        )

        # v2 autonomy modules: persistent experiment ledger + research journals.
        # All are additive and advisory — they enrich the THINK context but do
        # not change control flow unless explicitly enabled in config.
        self._ledger_cfg = config.get("ledger", {}) or {}
        self._stagnation_cfg = config.get("stagnation", {}) or {}
        self._journal_cfg = config.get("journal", {}) or {}
        self._safety_cfg = config.get("safety", {}) or {}
        self._gates_cfg = config.get("gates", {}) or {}
        self._strategy_cfg = config.get("strategy", {}) or {}
        self.ledger = (
            ExperimentLedger(self.workspace)
            if self._ledger_cfg.get("enabled", True)
            else None
        )
        self.journal = (
            ResearchJournal(self.workspace, max_chars=self._journal_cfg.get("max_chars", 4000))
            if self._journal_cfg.get("enabled", True)
            else None
        )

        # State
        self.cycle_count = self._load_cycle_counter()
        self.max_cycles = agent_config.get("max_cycles", -1)
        self.cooldown = agent_config.get("cooldown_interval", 300)
        self.no_progress_fallback_threshold = agent_config.get("no_progress_fallback_threshold", 3)
        # Proactive anti-burn: cap cycles started per rolling hour (0 = disabled).
        self.max_cycles_per_hour = agent_config.get("max_cycles_per_hour", 0)
        self._cycle_times_path = self.workspace / ".cycle_times"
        self._running = True
        self._no_progress_streak = 0
        self._last_no_progress_signature = ""

        # Graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _build_dispatchers(self, agent_config: dict) -> dict:
        """Build role-specific dispatchers while preserving legacy config."""
        default_provider = agent_config.get("provider", "anthropic")
        default_model = agent_config.get("model", "claude-sonnet-4-6")
        max_steps = agent_config.get("max_steps_per_cycle", 3)

        def make(role: str, default_role_provider: str = None) -> RoleDispatcher:
            provider = (
                agent_config.get(f"{role}_provider")
                or default_role_provider
                or default_provider
            )
            model = agent_config.get(f"{role}_model") or default_model
            role_provider_set = bool(agent_config.get(f"{role}_provider"))
            if (
                role_provider_set
                and not agent_config.get(f"{role}_model")
                and provider == "openai"
                and default_provider != "openai"
            ):
                model = {
                    "claude-sonnet-4-6": "codex-5.3",
                    "claude-opus-4-6": "gpt-5.4",
                }.get(model, model)
            base_url = agent_config.get(f"{role}_base_url") or agent_config.get("base_url", "")
            api_key_env = agent_config.get(f"{role}_api_key_env") or agent_config.get("api_key_env", "")
            auth_token_env = agent_config.get(
                f"{role}_auth_token_env",
            ) or agent_config.get("auth_token_env", "")
            return RoleDispatcher(
                model=model,
                provider=provider,
                max_steps=max_steps,
                base_url=base_url,
                api_key_env=api_key_env,
                auth_token_env=auth_token_env,
                workdir=str(self.project_dir),
            )

        code_provider = agent_config.get("code_provider") or default_provider
        return {
            "leader": make("leader"),
            "reflect": make("reflect", agent_config.get("leader_provider", default_provider)),
            "idea": make("idea"),
            "code": make("code", code_provider),
            "code_modify": make("code_modify", code_provider),
            "writing": make("writing"),
        }

    def run(self):
        """Main entry point. Runs the THINK → EXECUTE → REFLECT loop."""
        logger.info(f"Auto Researcher starting | project={self.project_dir} | cycle={self.cycle_count}")

        while self._running:
            if self.max_cycles > 0 and self.cycle_count >= self.max_cycles:
                logger.info(f"Reached max cycles ({self.max_cycles}). Stopping.")
                break

            self._throttle_if_needed()
            if not self._running:
                break

            self.cycle_count += 1
            self._save_cycle_counter()
            logger.info(f"=== Cycle {self.cycle_count} ===")

            try:
                # Keep leader context bounded to one cycle.
                self.dispatchers["leader"].reset_leader_history()
                self.dispatchers["reflect"].reset_leader_history()

                # Check for human directive
                directive = self._consume_directive()
                self._update_state(
                    {
                        "cycle": self.cycle_count,
                        "status": "planning",
                        "updated_at": time.time(),
                        "last_directive": directive or "",
                    }
                )

                # THINK: Analyze and plan
                think_result = self._think(directive)
                think_result = self._apply_strategy_routing(think_result, directive)
                think_result = self._apply_no_progress_fallback(think_result, directive)

                if think_result.get("action") == "wait":
                    logger.info("THINK decided to wait. Entering cooldown.")
                    self._update_state(
                        {
                            "cycle": self.cycle_count,
                            "status": "waiting",
                            "updated_at": time.time(),
                            "suggested_next_step": think_result.get("reason", ""),
                        }
                    )
                    self._smart_cooldown()
                    continue

                # EXECUTE: Run the plan
                execute_result = self._execute(think_result)

                if execute_result.get("experiment_launched"):
                    self._update_state(
                        {
                            "cycle": self.cycle_count,
                            "status": "running",
                            "pid": execute_result.get("pid"),
                            "log_file": execute_result.get("log_file", ""),
                            "started_at": time.time(),
                            "updated_at": time.time(),
                        }
                    )
                    # Monitor experiment (zero LLM cost)
                    monitor_result = self._monitor_experiment(execute_result)
                    experiment_status = monitor_result.get("status", "completed")
                    execute_result["training_logs"] = monitor_result.get("log_tail", "")
                    execute_result["final_metrics"] = monitor_result.get("metrics", {})
                    execute_result["experiment_status"] = experiment_status
                    execute_result["terminal_state"] = monitor_result.get("terminal_state", "")
                    self._update_state(
                        {
                            "status": experiment_status,
                            "pid": execute_result.get("pid"),
                            "log_file": execute_result.get("log_file", ""),
                            "updated_at": time.time(),
                            "terminal_state": monitor_result.get("terminal_state", ""),
                            "last_training_logs": monitor_result.get("log_tail", ""),
                            "last_metrics": monitor_result.get("metrics", {}),
                            "elapsed_hours": monitor_result.get("elapsed_hours"),
                        }
                    )

                # REFLECT: Evaluate and update
                reflect_result = self._reflect(execute_result)
                self._update_state(
                    {
                        "cycle": self.cycle_count,
                        "updated_at": time.time(),
                        "last_milestone": reflect_result.get("milestone", ""),
                        "last_decision": reflect_result.get("decision", ""),
                        "suggested_next_step": reflect_result.get("decision")
                        or reflect_result.get("reason")
                        or reflect_result.get("task", ""),
                        "last_error": "",
                    }
                )
                self._record_cycle_outcome(think_result, execute_result, reflect_result)
                self._record_to_ledger(think_result, execute_result, reflect_result)
                self._refresh_notes(reflect_result=reflect_result, directive=directive)

            except Exception as e:
                logger.error(f"Cycle {self.cycle_count} failed: {e}", exc_info=True)
                self.memory.log_decision(f"Cycle {self.cycle_count} error: {str(e)[:200]}")
                self._update_state(
                    {
                        "cycle": self.cycle_count,
                        "status": "error",
                        "updated_at": time.time(),
                        "last_error": str(e)[:500],
                    }
                )
                self._cooldown_after_error()

        logger.info("Auto Researcher stopped.")

    def _think(self, directive: Optional[str] = None) -> dict:
        """THINK phase: analyze current state and plan next experiment."""
        logger.info("THINK phase starting...")

        context = {
            "brief": self.memory.get_brief(),
            "memory_log": self.memory.get_log(),
            "cycle": self.cycle_count,
            "directive": directive,
        }
        self._enrich_context(context)

        result = self.dispatchers["leader"].dispatch_leader(
            task="think",
            context=context,
        )

        logger.info(f"THINK result: action={result.get('action', 'unknown')}")
        return result

    def _execute(self, plan: dict) -> dict:
        """EXECUTE phase: implement and run the planned experiment."""
        logger.info("EXECUTE phase starting...")

        agent_type = plan.get("agent", "code")
        task_description = plan.get("task", "")

        if agent_type == "code" and self._uses_builtin_code_launch():
            result = self._execute_code_with_builtin_launch(task_description)
        else:
            dispatcher = self.dispatchers.get(agent_type, self.dispatchers["code"])
            result = dispatcher.dispatch_worker(
                agent_type=agent_type,
                task=task_description,
                tool_registry=self.tools,
            )

        return result

    def _monitor_experiment(self, execute_result: dict) -> dict:
        """Monitor running experiment with ZERO LLM calls."""
        pid = execute_result.get("pid")
        log_file = execute_result.get("log_file")

        if not pid:
            return {"status": "no_pid"}

        logger.info(f"Monitoring experiment PID={pid}, log={log_file}")
        return self.monitor.wait_for_completion(
            pid=pid,
            log_file=log_file,
            notify=self.config.get("monitor", {}).get("notify_on_complete", True),
        )

    def _reflect(self, execute_result: dict) -> dict:
        """REFLECT phase: evaluate results and update memory."""
        logger.info("REFLECT phase starting...")

        context = {
            "brief": self.memory.get_brief(),
            "memory_log": self.memory.get_log(),
            "experiment_result": execute_result,
            "cycle": self.cycle_count,
        }
        self._enrich_context(context)

        result = self.dispatchers["reflect"].dispatch_leader(
            task="reflect",
            context=context,
        )

        # Update memory based on reflection
        if result.get("milestone"):
            self.memory.log_milestone(result["milestone"])
        if result.get("decision"):
            self.memory.log_decision(result["decision"])

        return result

    def _refresh_notes(self, reflect_result: dict, directive: Optional[str]):
        if not self.notes.is_enabled():
            return
        self.notes.refresh_dashboard(memory=self.memory, cycle_count=self.cycle_count)
        self.notes.append_daily_entry(
            memory=self.memory,
            cycle_count=self.cycle_count,
            event_type="cycle_complete",
            reflection=reflect_result,
            directive=directive,
        )

    def _uses_builtin_code_launch(self) -> bool:
        agent_config = self.config.get("agent", {}) or {}
        return agent_config.get("code_launch_provider", "") == "builtin"

    def _execute_code_with_builtin_launch(self, task_description: str) -> dict:
        """Let a code modifier prepare changes, then launch via ResearchToolRegistry.

        This path is designed for codex_cli: Codex may inspect and edit the repo,
        but it must hand back commands. The framework runs dry-run and launch so
        pid/log_file remain authoritative for monitoring.
        """
        handoff_instruction = """
## Controlled Launch Handoff
You may inspect and edit the repository, but do NOT start long-running training.
When code changes are ready, return exactly one JSON object with these fields:
{
  "status": "ready_to_launch",
  "changed_files": ["relative/path.py"],
  "dry_run_command": "short validation command, or empty string if unavailable",
  "launch_command": "training command for the framework to run",
  "log_file": "logs/experiment_name.log",
  "expected_duration": "short human-readable estimate"
}
If you cannot prepare a runnable experiment, return:
{"status": "blocked", "reason": "why"}
"""
        modifier = self.dispatchers["code_modify"]
        modify_result = modifier.dispatch_plain_worker(
            "code",
            task_description,
            extra_system=handoff_instruction,
        )
        handoff = self._parse_json_object(modify_result.get("response", ""))
        result = {
            "agent": "code",
            "response": modify_result.get("response", ""),
            "handoff": handoff,
            "code_launch_provider": "builtin",
        }

        if handoff.get("status") != "ready_to_launch":
            result["experiment_launched"] = False
            result["reason"] = handoff.get("reason", "code modifier did not return a launch handoff")
            return result

        dry_run_command = str(handoff.get("dry_run_command", "") or "").strip()
        if dry_run_command:
            dry_run_output = self.tools.execute_tool(
                "run_shell",
                {
                    "command": dry_run_command,
                    "timeout": int(self._strategy_cfg.get("dry_run_timeout", 300)),
                },
            )
            result["dry_run"] = self._safe_json_loads(dry_run_output)
            if not self._tool_result_ok(result["dry_run"]):
                result["experiment_launched"] = False
                result["reason"] = "dry-run failed"
                return result
        elif self._strategy_cfg.get("require_dry_run", True):
            result["experiment_launched"] = False
            result["reason"] = "dry-run command missing"
            return result

        launch_command = str(handoff.get("launch_command", "") or "").strip()
        log_file = str(handoff.get("log_file", "") or "").strip()
        if not launch_command or not log_file:
            result["experiment_launched"] = False
            result["reason"] = "launch_command or log_file missing"
            return result

        launch_args = {"command": launch_command, "log_file": log_file}
        if handoff.get("gpu"):
            launch_args["gpu"] = str(handoff["gpu"])
        launch_output = self.tools.execute_tool("launch_experiment", launch_args)
        payload = self._safe_json_loads(launch_output)
        result["launch"] = payload
        if isinstance(payload, dict) and payload.get("pid") is not None:
            result["experiment_launched"] = True
            result["pid"] = int(payload["pid"])
            result["log_file"] = payload.get("log_file", log_file)
        else:
            result["experiment_launched"] = False
            result["reason"] = payload.get("error", "launch failed") if isinstance(payload, dict) else "launch failed"
        return result

    @staticmethod
    def _parse_json_object(text: str) -> dict:
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            pass
        match = None
        for match in re.finditer(r"\{.*?\}", text or "", re.DOTALL):
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return {}

    @staticmethod
    def _safe_json_loads(text: str):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {"raw": text}

    @staticmethod
    def _tool_result_ok(result) -> bool:
        if not isinstance(result, dict):
            return True
        if result.get("error"):
            return False
        if result.get("returncode") not in (None, 0):
            return False
        return True

    def _apply_strategy_routing(self, think_result: dict, directive: Optional[str]) -> dict:
        """Deterministic routing guard layered on top of the leader plan."""
        if think_result.get("action") != "experiment":
            return think_result

        target = self._forced_agent_from_strategy(think_result, directive)
        if not target or target == think_result.get("agent"):
            return think_result

        routed = dict(think_result)
        original_agent = routed.get("agent", "code")
        routed["agent"] = target
        routed["routing_reason"] = f"strategy routed {original_agent} -> {target}"
        task = routed.get("task", "")
        if target == "idea":
            routed["task"] = (
                "Before running more code, search the literature and produce actionable "
                "hypotheses for the current project. Original plan: " + task
            )
        elif target == "code":
            routed["task"] = (
                "Use the latest idea/hypothesis notes and implement the next runnable "
                "experiment. Original plan: " + task
            )
        logger.info(routed["routing_reason"])
        return routed

    def _forced_agent_from_strategy(self, think_result: dict, directive: Optional[str]) -> Optional[str]:
        strategy = self._strategy_cfg
        if not strategy.get("enabled", True):
            return None

        directive_text = (directive or "").lower()
        if any(term in directive_text for term in ("paper", "literature", "arxiv", "论文", "文献")):
            return "idea"

        if strategy.get("require_initial_ideation", False) and not self._has_idea_output():
            return "idea"

        if strategy.get("idea_to_code_handoff", True) and self._last_ledger_status() == "idea":
            return "code"

        threshold = int(strategy.get("stagnation_cycles_before_idea", 0) or 0)
        if threshold > 0 and self._is_stagnating_for_strategy(threshold):
            return "idea"

        return None

    def _has_idea_output(self) -> bool:
        if self.ledger is None:
            return False
        return any(entry.get("status") == "idea" for entry in self.ledger.all())

    def _last_ledger_status(self) -> str:
        if self.ledger is None:
            return ""
        entries = self.ledger.all()
        return str(entries[-1].get("status", "")) if entries else ""

    def _is_stagnating_for_strategy(self, threshold: int) -> bool:
        metric_key = self._ledger_cfg.get("metric_key", "")
        if self.ledger is not None and metric_key:
            verdict = detect_stagnation(
                self.ledger.all(),
                metric_key,
                direction=self._ledger_cfg.get("metric_direction", "higher_better"),
                threshold_cycles=threshold,
                min_delta=self._stagnation_cfg.get("min_delta", 0.0),
            )
            return bool(verdict.get("stagnating"))
        return self._no_progress_streak >= threshold

    def _plan_signature(self, plan: dict) -> str:
        """Build a stable signature for repeated-plan detection."""
        normalized = {
            "action": plan.get("action", ""),
            "agent": plan.get("agent", ""),
            "task": " ".join(plan.get("task", "").split())[:300],
            "hypothesis": " ".join(plan.get("hypothesis", "").split())[:200],
        }
        return json.dumps(normalized, sort_keys=True, ensure_ascii=True)

    def _apply_no_progress_fallback(self, think_result: dict, directive: Optional[str]) -> dict:
        """Back off if the same experiment plan keeps repeating without progress."""
        if directive or self.no_progress_fallback_threshold <= 0:
            return think_result

        if think_result.get("action") != "experiment":
            return think_result

        signature = self._plan_signature(think_result)
        if (
            self._no_progress_streak >= self.no_progress_fallback_threshold
            and signature == self._last_no_progress_signature
        ):
            reason = (
                f"Fallback triggered after {self._no_progress_streak} no-progress cycles on the same plan. "
                "Backing off to avoid empty loops until new signal arrives."
            )
            logger.warning(reason)
            self.memory.log_decision(reason)
            if self.journal is not None:
                task_text = " ".join(think_result.get("task", "").split())[:160]
                self.journal.append_dead_end(
                    f"Cycle {self.cycle_count}: repeated with no progress — {task_text}"
                )
            return {
                "action": "wait",
                "reason": reason,
                "decision": reason,
            }

        return think_result

    def _record_cycle_outcome(self, think_result: dict, execute_result: dict, reflect_result: dict):
        """Track whether repeated cycles are producing real progress."""
        if think_result.get("action") != "experiment":
            if think_result.get("action") != "wait":
                self._no_progress_streak = 0
                self._last_no_progress_signature = ""
            return

        signature = self._plan_signature(think_result)
        made_progress = bool(
            execute_result.get("experiment_launched")
            or execute_result.get("final_metrics")
            or reflect_result.get("milestone")
        )

        if made_progress:
            self._no_progress_streak = 0
            self._last_no_progress_signature = ""
            return

        if signature == self._last_no_progress_signature:
            self._no_progress_streak += 1
        else:
            self._last_no_progress_signature = signature
            self._no_progress_streak = 1

    def _enrich_context(self, context: dict):
        """Add advisory v2 signals (ledger / stagnation / journals / violations /
        gate) to a leader context dict. All keys are optional and only added when
        the corresponding feature is enabled and has something to report."""
        if self.ledger is not None:
            try:
                summary = self.ledger.summary(self._ledger_cfg.get("recent_in_context", 5))
                if summary:
                    context["recent_experiments"] = summary
            except Exception as exc:  # never let context-building break a cycle
                logger.warning(f"ledger summary failed: {exc}")

            metric_key = self._ledger_cfg.get("metric_key", "")
            direction = self._ledger_cfg.get("metric_direction", "higher_better")

            if metric_key and self._stagnation_cfg.get("enabled", True):
                try:
                    verdict = detect_stagnation(
                        self.ledger.all(),
                        metric_key,
                        direction=direction,
                        threshold_cycles=self._stagnation_cfg.get("threshold_cycles", 3),
                        min_delta=self._stagnation_cfg.get("min_delta", 0.0),
                    )
                    context["progress_signal"] = self._format_stagnation(verdict)
                except Exception as exc:
                    logger.warning(f"stagnation detection failed: {exc}")

            if metric_key and self._gates_cfg.get("enabled", False):
                try:
                    gate = check_phase_gate(
                        self.ledger.all(),
                        metric_key,
                        threshold=self._gates_cfg.get("threshold", 0.0),
                        direction=self._gates_cfg.get("direction", direction),
                    )
                    context["phase_gate"] = self._format_gate(gate)
                except Exception as exc:
                    logger.warning(f"phase gate check failed: {exc}")

        if self.journal is not None:
            try:
                tail_chars = int(self._journal_cfg.get("tail_in_context", 1500))
                dead_ends = self.journal.dead_ends_tail(tail_chars)
                if "- [" in dead_ends:
                    context["dead_ends"] = dead_ends.strip()
                insights = self.journal.insights_tail(tail_chars)
                if "- [" in insights:
                    context["insights"] = insights.strip()
            except Exception as exc:  # never let an advisory signal break a cycle
                logger.warning(f"journal tail failed: {exc}")

        if self._safety_cfg.get("enabled", True):
            try:
                violations = safety.scan_violations(
                    self._load_state(),
                    self._no_progress_streak,
                    time.time(),
                    fail_threshold=self._safety_cfg.get("fail_threshold", 3),
                    stale_state_hours=self._safety_cfg.get("stale_state_hours", 6),
                )
                if violations:
                    context["active_violations"] = "\n".join(f"- {v}" for v in violations)
            except Exception as exc:
                logger.warning(f"violation scan failed: {exc}")

    @staticmethod
    def _format_stagnation(verdict: dict) -> str:
        if verdict.get("reason"):
            return f"{verdict['reason']} (metric={verdict.get('metric_key', '')})"
        flag = "STAGNATING" if verdict.get("stagnating") else "improving"
        return (
            f"{flag}: best {verdict.get('metric_key')}={verdict.get('best')}, "
            f"{verdict.get('cycles_since_improvement')} cycle(s) since last improvement "
            f"over {verdict.get('n_points')} measured runs."
        )

    @staticmethod
    def _format_gate(gate: dict) -> str:
        if gate.get("gate_met"):
            return f"Phase gate MET (best metric={gate.get('best_metric')}). OK to pursue innovation."
        return f"Phase gate NOT met: {gate.get('blocker_reason', 'baseline quality not reached')}."

    def _record_to_ledger(self, think_result: dict, execute_result: dict, reflect_result: dict):
        """Append this cycle's outcome to the experiment ledger and capture a
        durable insight when the reflection produced a milestone."""
        if self.ledger is None:
            return
        metrics = execute_result.get("final_metrics") or {}
        if not isinstance(metrics, dict):
            metrics = {}
        if execute_result.get("experiment_launched"):
            # Prefer the monitor's real outcome (completed / failed) over a
            # generic "launched" so the ledger reflects what actually happened.
            status = execute_result.get("experiment_status") or "launched"
        elif execute_result.get("agent") in ("idea", "writing"):
            status = execute_result.get("agent")
        else:
            status = think_result.get("action", "") or "no_experiment"
        terminal_state = execute_result.get("terminal_state", "")
        conclusion = reflect_result.get("milestone") or reflect_result.get("decision", "")
        if status == "failed" and terminal_state:
            conclusion = (f"[{terminal_state}] " + conclusion).strip()
        try:
            self.ledger.record(
                cycle=self.cycle_count,
                hypothesis=think_result.get("hypothesis") or think_result.get("task", ""),
                action=think_result.get("action", ""),
                status=status,
                metrics=metrics,
                pid=execute_result.get("pid"),
                log_file=execute_result.get("log_file", ""),
                conclusion=conclusion,
            )
        except Exception as exc:
            logger.warning(f"ledger record failed: {exc}")

        if self.journal is not None and reflect_result.get("milestone"):
            self.journal.append_insight(reflect_result["milestone"])

    def _load_cycle_times(self) -> list:
        if self._cycle_times_path.exists():
            try:
                data = json.loads(self._cycle_times_path.read_text())
                if isinstance(data, list):
                    return [float(t) for t in data]
            except (json.JSONDecodeError, ValueError, TypeError):
                return []
        return []

    def _save_cycle_times(self, timestamps: list):
        try:
            self._cycle_times_path.write_text(json.dumps(timestamps))
        except OSError as exc:  # pragma: no cover - disk failure path
            logger.warning(f"failed to persist cycle times: {exc}")

    def _throttle_if_needed(self):
        """Proactive anti-burn: sleep so the agent never exceeds
        max_cycles_per_hour. No-op (and no state writes) when disabled."""
        if not self.max_cycles_per_hour or self.max_cycles_per_hour <= 0:
            return
        now = time.time()
        timestamps = self._load_cycle_times()
        wait = safety.seconds_until_allowed(timestamps, now, self.max_cycles_per_hour)
        if wait > 0:
            logger.warning(
                f"Anti-burn: {self.max_cycles_per_hour} cycles/hour reached; "
                f"throttling for {int(wait)}s"
            )
            elapsed = 0.0
            while elapsed < wait and self._running:
                chunk = min(30.0, wait - elapsed)
                time.sleep(chunk)
                elapsed += chunk
            now = time.time()
        timestamps = safety.prune_timestamps(timestamps, now)
        timestamps.append(now)
        self._save_cycle_times(timestamps)

    def _smart_cooldown(self):
        """Poll at short intervals instead of fixed long wait."""
        logger.info(f"Smart cooldown: polling every {self.cooldown}s")
        elapsed = 0
        while elapsed < self.cooldown and self._running:
            time.sleep(min(60, self.cooldown - elapsed))
            elapsed += 60

            # Check if any experiment just finished
            if self.monitor.has_completed_experiments():
                logger.info("Experiment completed during cooldown. Waking up.")
                return

    def _cooldown_after_error(self):
        """Back off after an error to prevent burn loops."""
        backoff = min(self.cooldown * 2, 1800)  # Max 30 min
        logger.warning(f"Error backoff: waiting {backoff}s")
        time.sleep(backoff)

    def _consume_directive(self) -> Optional[str]:
        """Read and consume HUMAN_DIRECTIVE.md if present."""
        directive_path = self.workspace / "HUMAN_DIRECTIVE.md"
        if directive_path.exists():
            content = directive_path.read_text().strip()
            if content:
                # Archive the directive
                archive_dir = self.workspace / "directive_archive"
                archive_dir.mkdir(exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                directive_path.rename(archive_dir / f"directive_{timestamp}.md")
                logger.info(f"Consumed directive: {content[:100]}...")
                return content
        return None

    def _load_cycle_counter(self) -> int:
        counter_file = self.workspace / ".cycle_counter"
        if counter_file.exists():
            return int(counter_file.read_text().strip())
        return 0

    def _save_cycle_counter(self):
        counter_file = self.workspace / ".cycle_counter"
        counter_file.write_text(str(self.cycle_count))

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def _update_state(self, updates: dict):
        state = self._load_state()
        state.update(updates)
        self.state_path.write_text(json.dumps(state, indent=2))

    def _handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}. Initiating graceful shutdown.")
        self._running = False


def main():
    parser = argparse.ArgumentParser(description="Auto Researcher - Autonomous ML Experiment Runner")
    parser.add_argument("--project", type=str, default=".", help="Path to project directory")
    parser.add_argument("--config", type=str, default="config.yaml", help="Config file path")
    parser.add_argument("--max-cycles", type=int, default=None, help="Override max cycles")
    parser.add_argument("--gpu", type=str, default=None, help="GPU device(s) to use")
    parser.add_argument("--directive", type=str, default="", help="One-cycle human directive")
    parser.add_argument("--check", action="store_true", help="Verify installation and exit")

    args = parser.parse_args()

    if args.check:
        print("Auto Researcher installation check:")
        print(f"  Python: {sys.version}")
        print(f"  Project: {args.project}")
        print("  Status: OK")
        return

    # Load config
    import yaml
    config_path = Path(args.project) / args.config
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    if args.max_cycles is not None:
        config.setdefault("agent", {})["max_cycles"] = args.max_cycles

    if args.gpu is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu

    if args.directive:
        workspace_name = config.get("project", {}).get("workspace", "workspace")
        workspace = Path(args.project) / workspace_name
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "HUMAN_DIRECTIVE.md").write_text(args.directive.strip() + "\n")

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(Path(args.project) / "auto_researcher.log"),
        ],
    )

    # Run
    loop = AutoResearcher(config=config, project_dir=args.project)
    loop.run()


if __name__ == "__main__":
    main()
