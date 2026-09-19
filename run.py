#!/usr/bin/env python3
"""Root-level entrypoint for ModueHarness.

Allows executing the harness directly without setting PYTHONPATH or installing via pip.
Usage:
    python run.py -i -P my-web-app
    python run.py "작업 내용" -P my-app
"""

from pathlib import Path
import sys

# Ensure src/ directory is on sys.path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from modue_harness.cli import main

if __name__ == "__main__":
    sys.exit(main())
