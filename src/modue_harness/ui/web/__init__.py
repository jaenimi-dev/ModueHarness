"""NiceGUI Web UI integration for ModueHarness."""

from typing import Optional
from modue_harness.ui.controller import UIController


def launch_web_ui(
    controller: Optional[UIController] = None,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
) -> None:
    """Launch the ModueHarness NiceGUI Web UI."""
    try:
        from modue_harness.ui.web.app import run_app
    except ImportError as e:
        if "nicegui" in str(e).lower():
            raise ImportError(
                "NiceGUI is required to run the Web UI.\n"
                "Please install it with: pip install 'modue-harness[ui]' (or pip install nicegui)"
            ) from e
        raise

    run_app(controller=controller, host=host, port=port, open_browser=open_browser)
