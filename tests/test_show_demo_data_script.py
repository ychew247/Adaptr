import subprocess
import sys


def test_show_demo_data_script_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/show_demo_data.py"],
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert "DATABASE_URL is not set" in result.stderr
