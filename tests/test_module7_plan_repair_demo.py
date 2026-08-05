import subprocess
import sys


def test_module7_plan_repair_demo_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/module7_plan_repair_demo.py", "--skip-live"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Module 7 plan repair demo imports successfully." in result.stdout
