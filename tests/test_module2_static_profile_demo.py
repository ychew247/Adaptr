import subprocess
import sys


def test_module2_static_profile_demo_imports_project_modules_when_run_by_path():
    result = subprocess.run(
        [sys.executable, "scripts/module2_static_profile_demo.py"],
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert "DATABASE_URL is not set" in result.stderr
