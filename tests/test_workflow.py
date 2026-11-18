"""Exercise the workflow's actual send commands without sending email."""

import os
from pathlib import Path
import shutil
import subprocess
import textwrap
import unittest


if os.name == "nt":
    bash = str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe")
    if not Path(bash).is_file():
        bash = None
else:
    bash = shutil.which("bash")


@unittest.skipUnless(bash, "Bash is needed to check GitHub Actions shell commands")
class WorkflowTests(unittest.TestCase):
    def commands_for(self, event_name, menu_date=""):
        workflow = Path(__file__).resolve().parents[1] / ".github/workflows/lunch-menu.yml"
        script = textwrap.dedent(workflow.read_text().split("        run: |\n", 1)[1])
        # Replace Python with a shell function that records its arguments.
        stub = 'python() { printf "%s\\n" "$@"; }\n'
        result = subprocess.run(
            [bash, "--noprofile", "--norc", "-c", stub + script],
            env={**os.environ, "EVENT_NAME": event_name, "MENU_DATE": menu_date},
            capture_output=True, text=True, check=True,
        )
        return result.stdout.splitlines()

    def test_scheduled_run_sends_tomorrow_without_test_prefix_or_date_override(self):
        self.assertEqual(
            self.commands_for("schedule", "2026-11-19"),
            ["notify.py", "--scheduled", "--send"],
        )

    def test_manual_run_with_date_keeps_test_prefix(self):
        self.assertEqual(
            self.commands_for("workflow_dispatch", "2026-11-19"),
            ["notify.py", "--date", "2026-11-19", "--test", "--send"],
        )

    def test_manual_run_without_date_uses_tomorrow_and_keeps_test_prefix(self):
        self.assertEqual(
            self.commands_for("workflow_dispatch"),
            ["notify.py", "--test", "--send"],
        )


if __name__ == "__main__":
    unittest.main()
