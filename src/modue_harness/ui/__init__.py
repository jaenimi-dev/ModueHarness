"""ModueHarness UI package.

Provides foundation and launch handlers for:
- NiceGUI Web UI (`modue-harness ui` / `python run.py --ui`)
- Textual Terminal TUI (`modue-harness tui` / `python run.py --tui`)
"""

from modue_harness.ui.controller import UIController

__all__ = ["UIController"]
