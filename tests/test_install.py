import tempfile
import unittest
from pathlib import Path

import install


class InstallHelpersTests(unittest.TestCase):
    def test_build_codex_skill_text_strips_argument_hint(self):
        source = """---
name: auto-research
description: "Launch experiment loop"
argument-hint: "[--project <path>]"
---

# /auto-research

Body text.
"""
        rendered = install._build_codex_skill_text(source)

        self.assertNotIn("argument-hint", rendered)
        self.assertIn("$auto-research", rendered)
        self.assertIn("# /auto-research", rendered)

    def test_install_and_uninstall_cover_claude_and_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            claude_dir = root / ".claude"
            codex_dir = root / ".codex"

            (repo / "skills" / "auto-research" / "agents").mkdir(parents=True)
            (repo / "auto_researcher" / "gpu").mkdir(parents=True)
            (repo / "prompts").mkdir(parents=True)

            (repo / "skills" / "auto-research" / "SKILL.md").write_text(
                """---
name: auto-research
description: "Launch experiment loop"
argument-hint: "[--project <path>]"
---

# /auto-research

Body text.
"""
            )
            (repo / "skills" / "auto-research" / "agents" / "openai.yaml").write_text(
                'interface:\n  display_name: "Auto Experiment"\n'
            )
            (repo / "auto_researcher" / "runner.py").write_text("print('runner')\n")
            (repo / "auto_researcher" / "gpu" / "detect.py").write_text("print('gpu')\n")
            (repo / "prompts" / "leader.md").write_text("# Leader\n")
            (repo / "config.yaml").write_text("agent:\n  provider: anthropic\n")

            install.install(claude_dir=claude_dir, codex_dir=codex_dir, repo_dir=repo)

            claude_skill = claude_dir / "commands" / "auto-research.md"
            codex_skill = codex_dir / "skills" / "auto-research" / "SKILL.md"
            codex_ui_meta = codex_dir / "skills" / "auto-research" / "agents" / "openai.yaml"
            codex_runtime = codex_dir / "auto_researcher" / "auto_researcher" / "runner.py"
            codex_prompt = codex_dir / "auto_researcher" / "prompts" / "leader.md"

            self.assertTrue(claude_skill.exists())
            self.assertIn("argument-hint", claude_skill.read_text())

            self.assertTrue(codex_skill.exists())
            self.assertNotIn("argument-hint", codex_skill.read_text())
            self.assertIn("$auto-research", codex_skill.read_text())

            self.assertTrue(codex_ui_meta.exists())
            self.assertTrue(codex_runtime.exists())
            self.assertTrue(codex_prompt.exists())

            install.uninstall(claude_dir=claude_dir, codex_dir=codex_dir, repo_dir=repo)

            self.assertFalse(claude_skill.exists())
            self.assertFalse((codex_dir / "skills" / "auto-research").exists())
            self.assertFalse((codex_dir / "auto_researcher").exists())

    def test_install_refuses_to_overwrite_unowned_codex_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            claude_dir = root / ".claude"
            codex_dir = root / ".codex"

            (repo / "skills" / "auto-research").mkdir(parents=True)
            (repo / "auto_researcher").mkdir(parents=True)
            (repo / "prompts").mkdir(parents=True)
            (repo / "skills" / "auto-research" / "SKILL.md").write_text(
                """---
name: auto-research
description: "Launch experiment loop"
---

Body.
"""
            )
            (repo / "config.yaml").write_text("agent:\n  provider: anthropic\n")
            foreign_skill = codex_dir / "skills" / "auto-research"
            foreign_skill.mkdir(parents=True)
            (foreign_skill / "SKILL.md").write_text("foreign\n")

            with self.assertRaises(RuntimeError):
                install.install(claude_dir=claude_dir, codex_dir=codex_dir, repo_dir=repo)

            self.assertFalse((claude_dir / "commands" / "auto-research.md").exists())


if __name__ == "__main__":
    unittest.main()
