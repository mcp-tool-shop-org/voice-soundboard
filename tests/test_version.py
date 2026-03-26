"""Version alignment tests."""

import re
from pathlib import Path

import voice_soundboard


def _pyproject_version() -> str:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    for line in pyproject.read_text().splitlines():
        if line.startswith("version"):
            return line.split('"')[1]
    raise RuntimeError("version not found in pyproject.toml")


def test_init_version_matches_pyproject():
    assert voice_soundboard.__version__ == _pyproject_version()


def test_version_is_valid_semver():
    assert re.match(r"^\d+\.\d+\.\d+$", voice_soundboard.__version__)


def test_version_command():
    from voice_soundboard.adapters.cli import main
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main(["version"])
    assert voice_soundboard.__version__ in buf.getvalue()
