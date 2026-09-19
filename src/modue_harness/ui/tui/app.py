"""Textual Terminal UI Application implementation for ModueHarness."""

from typing import Optional
from modue_harness.ui.controller import UIController


def run_tui_app(controller: Optional[UIController] = None) -> None:
    """Run Textual TUI application."""
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Container, Horizontal, Vertical
        from textual.widgets import (
            Button,
            Footer,
            Header,
            Input,
            Label,
            ListItem,
            ListView,
            RichLog,
            Static,
            TabbedContent,
            TabPane,
        )
    except ImportError as e:
        raise ImportError(
            "Textual is not installed. Please install it using: pip install 'modue-harness[ui]' or pip install textual"
        ) from e

    ctrl = controller or UIController()

    class ModueHarnessTUI(App):
        """ModueHarness Interactive Terminal Dashboard."""

        CSS = """
        Screen {
            layout: horizontal;
            background: $surface;
        }

        #left-sidebar {
            width: 35%;
            border-right: heavy $accent;
            padding: 1;
        }

        #right-container {
            width: 65%;
            padding: 1;
        }

        #prompt-input {
            margin-bottom: 1;
        }

        .section-title {
            text-style: bold;
            color: $accent;
            margin-bottom: 1;
        }

        #log-view {
            border: solid $primary;
            height: 100%;
            background: $panel;
        }
        """

        BINDINGS = [
            ("q", "quit", "Quit"),
            ("c", "cancel_task", "Cancel"),
        ]

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal():
                with Vertical(id="left-sidebar"):
                    yield Label(f"🎯 Project: {ctrl.project_name}", classes="section-title")
                    yield Input(placeholder="Enter command for AI team...", id="prompt-input")
                    with Horizontal():
                        yield Button("Run", variant="primary", id="btn-run")
                        yield Button("Run &", variant="secondary", id="btn-async")
                        yield Button("Cancel", variant="error", id="btn-cancel")

                    yield Label("👥 AI Team Members", classes="section-title")
                    team_list = ListView(id="team-list")
                    for a in ctrl.get_agents_info():
                        team_list.append(ListItem(Label(f"• {a['name']} ({a['adapter']})")))
                    yield team_list

                with Vertical(id="right-container"):
                    with TabbedContent():
                        with TabPane("Live Stream"):
                            yield RichLog(id="log-view", highlight=True, markup=True)
                        with TabPane("Artifacts"):
                            yield Static("Artifacts will appear here after task completion.", id="artifact-view")
                        with TabPane("Project Files"):
                            yield Static(f"Files in projects/{ctrl.project_name}", id="files-view")

            yield Footer()

        def on_mount(self) -> None:
            self.title = f"ModueHarness TUI - {ctrl.project_name}"
            log = self.query_one("#log-view", RichLog)
            log.write("[bold green]ModueHarness TUI Loaded.[/bold green] Ready for commands.")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            log = self.query_one("#log-view", RichLog)
            inp = self.query_one("#prompt-input", Input)
            cmd = inp.value.strip()

            if event.button.id == "btn-run":
                if not cmd:
                    return
                log.write(f"\n[bold yellow]>>> Running:[/bold yellow] {cmd}")
                res = ctrl.execute_command(cmd)
                status_color = "green" if res.get("success") else "red"
                log.write(f"[{status_color}]Finished: {res.get('status')} ({res.get('total_duration_sec', 0.0):.1f}s)[/{status_color}]")
                if not res.get("success") and res.get("error"):
                    log.write(f"[red]Error: {res.get('error')}[/red]")
                inp.value = ""

            elif event.button.id == "btn-async":
                if not cmd:
                    return
                job = ctrl.execute_command_async(cmd)
                log.write(f"\n[bold cyan]>>> Background Job Dispatched: {job.id}[/bold cyan]")
                inp.value = ""

            elif event.button.id == "btn-cancel":
                ctrl.cancel_job()
                log.write("\n[bold red]Task cancellation requested.[/bold red]")

        def action_cancel_task(self) -> None:
            ctrl.cancel_job()
            log = self.query_one("#log-view", RichLog)
            log.write("\n[bold red]Task cancellation requested via 'c'.[/bold red]")

    app = ModueHarnessTUI()
    try:
        app.run()
    except (KeyboardInterrupt, Exception):
        pass
