import subprocess
import sys


def test_run_module_script_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/run_module.py", "--module", "4", "--skip-live"],
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert "Direct module runner imports successfully." in result.stdout


def test_run_module_script_accepts_module7_without_running_live_dependencies():
    result = subprocess.run(
        [sys.executable, "scripts/run_module.py", "--module", "7", "--skip-live"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Direct module runner imports successfully." in result.stdout


def test_run_module_script_accepts_replace_goal_option_without_running_live_dependencies():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_module.py",
            "--module",
            "3",
            "--replace-goal",
            "--skip-live",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
