import os
import subprocess
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "_scripts"
SCRIPTS = ["setup.sh", "run.sh", "lint.sh", "test.sh", "update.sh"]
SHARED_LIB = SCRIPTS_DIR / "lib" / "shared.sh"


@pytest.mark.parametrize("name", SCRIPTS)
def test_script_exists_and_is_executable(name):
    script = SCRIPTS_DIR / name
    assert script.is_file(), f"{script} is missing"
    assert os.access(script, os.X_OK), f"{script} is not executable"


@pytest.mark.parametrize("name", [*SCRIPTS, "lib/shared.sh"])
def test_script_has_valid_bash_syntax(name):
    result = subprocess.run(["bash", "-n", str(SCRIPTS_DIR / name)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name", SCRIPTS)
def test_script_sources_shared_lib(name):
    content = (SCRIPTS_DIR / name).read_text()
    assert "lib/shared.sh" in content


def test_shared_lib_defines_paths():
    result = subprocess.run(
        ["bash", "-c", f'source "{SHARED_LIB}" && echo "$ROOT_DIR" && echo "$VENV_DIR"'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    root, venv = result.stdout.splitlines()
    assert Path(root) == SCRIPTS_DIR.parent
    assert Path(venv) == SCRIPTS_DIR.parent / ".venv"


def test_update_script_restricts_package_age():
    content = (SCRIPTS_DIR / "update.sh").read_text()
    assert 'export PIP_UPLOADED_PRIOR_TO="$MIN_PACKAGE_AGE"' in content
    assert "pip_supports_upload_cutoff" in content


def test_shared_lib_default_min_package_age_is_one_day():
    result = subprocess.run(
        ["bash", "-c", f'unset MIN_PACKAGE_AGE; source "{SHARED_LIB}" && echo "$MIN_PACKAGE_AGE"'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "P1D"


def test_run_script_runs_program_from_any_directory(tmp_path):
    result = subprocess.run(
        [str(SCRIPTS_DIR / "run.sh"), "hello"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "Hello, world" in result.stdout
