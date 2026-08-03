import subprocess
import sys


def test_module4_adaptive_checkin_demo_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/module4_adaptive_checkin_demo.py", "--skip-live"],
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert "Module 4 parser: Ollama" in result.stdout
    assert "Module 4 adaptive check-in demo imports successfully." in result.stdout
