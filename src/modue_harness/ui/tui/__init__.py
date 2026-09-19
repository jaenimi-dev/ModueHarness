"""Textual Terminal UI (TUI) integration for ModueHarness."""

from typing import Optional
from modue_harness.ui.controller import UIController


def launch_tui(controller: Optional[UIController] = None) -> None:
    """Launch the ModueHarness Textual Terminal UI."""
    try:
        from modue_harness.ui.tui.app import run_tui_app
    except ImportError as e:
        if "textual" in str(e).lower():
            raise ImportError(
                "Textual is required to run the Terminal UI (TUI).\n"
                "Please install it with: pip install 'modue-harness[ui]' (or pip install textual)"
            ) from e
        raise

    run_tui_app(controller=controller)
