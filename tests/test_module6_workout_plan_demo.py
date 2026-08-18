import subprocess
import sys


def test_module6_workout_plan_demo_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/module6_workout_plan_demo.py", "--skip-live"],
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert "Module 6 workout plan demo imports successfully." in result.stdout
