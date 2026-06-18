import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from auto_researcher.runner import AutoResearcher


class AutoResearcherFallbackTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.tempdir.name)
        (self.project_dir / "PROJECT_BRIEF.md").write_text("Test brief")
        self.loop = AutoResearcher(
            config={
                "project": {"workspace": "workspace"},
                "agent": {
                    "max_cycles": 1,
                    "cooldown_interval": 0,
                    "no_progress_fallback_threshold": 2,
                },
                "obsidian": {"enabled": False},
            },
            project_dir=str(self.project_dir),
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_run_resets_leader_history_each_cycle(self):
        self.loop.dispatcher.reset_leader_history = Mock()
        self.loop._think = lambda directive=None: {"action": "wait", "reason": "idle"}
        self.loop._smart_cooldown = lambda: None

        self.loop.run()

        self.loop.dispatcher.reset_leader_history.assert_called_once()

    def test_repeated_no_progress_plan_triggers_wait_fallback(self):
        plan = {
            "action": "experiment",
            "agent": "code",
            "task": "Retry the same broken command",
            "hypothesis": "It might work this time",
        }
        execute_result = {"experiment_launched": False}
        reflect_result = {}

        self.loop._record_cycle_outcome(plan, execute_result, reflect_result)
        self.loop._record_cycle_outcome(plan, execute_result, reflect_result)

        fallback = self.loop._apply_no_progress_fallback(plan, directive=None)

        self.assertEqual(fallback["action"], "wait")
        self.assertIn("Fallback triggered", fallback["reason"])

    def test_strategy_routes_initial_cycle_to_idea(self):
        self.loop._strategy_cfg = {
            "enabled": True,
            "require_initial_ideation": True,
        }
        plan = {"action": "experiment", "agent": "code", "task": "run training"}

        routed = self.loop._apply_strategy_routing(plan, directive=None)

        self.assertEqual(routed["agent"], "idea")
        self.assertIn("literature", routed["task"])

    def test_strategy_routes_after_idea_to_code(self):
        self.loop.ledger.record(cycle=1, action="experiment", status="idea", hypothesis="search papers")
        self.loop._strategy_cfg = {
            "enabled": True,
            "idea_to_code_handoff": True,
        }
        plan = {"action": "experiment", "agent": "idea", "task": "more search"}

        routed = self.loop._apply_strategy_routing(plan, directive=None)

        self.assertEqual(routed["agent"], "code")
        self.assertIn("routed", routed["routing_reason"])

    def test_builtin_code_launch_runs_dry_run_then_launch(self):
        handoff = {
            "status": "ready_to_launch",
            "changed_files": ["train.py"],
            "dry_run_command": "python train.py --max_steps 2",
            "launch_command": "python train.py",
            "log_file": "logs/exp.log",
        }
        modifier = Mock()
        modifier.dispatch_plain_worker.return_value = {"agent": "code", "response": __import__("json").dumps(handoff)}
        self.loop.dispatchers["code_modify"] = modifier
        self.loop._strategy_cfg = {"require_dry_run": True, "dry_run_timeout": 42}
        self.loop.tools.execute_tool = Mock(side_effect=[
            '{"returncode": 0, "stdout": "ok"}',
            '{"pid": 123, "log_file": "logs/exp.log"}',
        ])

        result = self.loop._execute_code_with_builtin_launch("change code")

        self.assertTrue(result["experiment_launched"])
        self.assertEqual(result["pid"], 123)
        self.assertEqual(self.loop.tools.execute_tool.call_args_list[0].args[0], "run_shell")
        self.assertEqual(self.loop.tools.execute_tool.call_args_list[1].args[0], "launch_experiment")

    def test_builtin_code_launch_blocks_when_dry_run_missing(self):
        handoff = {
            "status": "ready_to_launch",
            "launch_command": "python train.py",
            "log_file": "logs/exp.log",
        }
        modifier = Mock()
        modifier.dispatch_plain_worker.return_value = {"agent": "code", "response": __import__("json").dumps(handoff)}
        self.loop.dispatchers["code_modify"] = modifier
        self.loop._strategy_cfg = {"require_dry_run": True}
        self.loop.tools.execute_tool = Mock()

        result = self.loop._execute_code_with_builtin_launch("change code")

        self.assertFalse(result["experiment_launched"])
        self.assertIn("dry-run", result["reason"])
        self.loop.tools.execute_tool.assert_not_called()


if __name__ == "__main__":
    unittest.main()
