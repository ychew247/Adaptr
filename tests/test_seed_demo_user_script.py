import subprocess
import sys


def test_seed_demo_user_script_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/seed_demo_user.py"],
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert "DATABASE_URL is not set" in result.stderr
