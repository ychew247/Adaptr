import subprocess
import sys


def test_module5_readiness_demo_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/module5_readiness_demo.py", "--skip-live"],
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert "Module 5 readiness demo imports successfully." in result.stdout
