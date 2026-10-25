import subprocess
import sys

from typer.testing import CliRunner

from ankivis.cli import app

runner = CliRunner()


def test_hello_prints_hello_world():
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "Hello, world" in result.output


def test_help_lists_hello_command():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "hello" in result.output


def test_module_is_executable():
    result = subprocess.run(
        [sys.executable, "-m", "ankivis", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "hello" in result.stdout
