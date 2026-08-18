import subprocess
import sys


def test_ollama_smoke_script_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/test_ollama_connection.py", "--skip-live"],
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert "Ollama smoke script imports successfully." in result.stdout
