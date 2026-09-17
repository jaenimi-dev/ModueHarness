"""Tests verifying version formatting and consistency."""

import re
from pathlib import Path

import modue_harness


def test_version_format():
    """Verify __version__ adheres to semantic versioning (X.Y.Z)."""
    semver_pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$"
    assert re.match(
        semver_pattern, modue_harness.__version__
    ), f"Invalid SemVer version: {modue_harness.__version__}"


def test_version_value():
    """Verify the current version is 0.3.0."""
    assert modue_harness.__version__ == "0.3.0"


def test_pyproject_version_matches():
    """Verify pyproject.toml contains the same version string."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject_path.exists()
    content = pyproject_path.read_text(encoding="utf-8")
    assert f'version = "{modue_harness.__version__}"' in content
