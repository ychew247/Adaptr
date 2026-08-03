import subprocess
import sys


def test_module3_ollama_goal_setup_demo_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/module3_goal_setup_ollama_demo.py", "--skip-live"],
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert "Module 3 Ollama demo imports successfully." in result.stdout
    assert "Module 3 parser: Ollama" in result.stdout
