import subprocess
import sys


def test_module3_goal_setup_demo_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/module3_goal_setup_demo.py"],
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert "DATABASE_URL is not set" in result.stderr
