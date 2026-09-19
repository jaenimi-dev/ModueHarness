"""NiceGUI Web UI Application implementation for ModueHarness."""

import asyncio
import inspect
from typing import Optional
from modue_harness.ui.controller import UIController


def run_app(
    controller: Optional[UIController] = None,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
) -> None:
    """Run NiceGUI dashboard application."""
    try:
        from nicegui import app, ui
    except ImportError as e:
        raise ImportError(
            "NiceGUI is not installed. Please install it using: pip install 'modue-harness[ui]' or pip install nicegui"
        ) from e

    ctrl = controller or UIController()

    def build_dashboard() -> None:
        """Construct the 3-column dashboard UI layout for each connecting client."""
        # Dark mode by default
        dark = ui.dark_mode(value=True)

        # 1. Header
        with ui.header().classes("items-center justify-between bg-slate-900 text-white px-4 py-2 border-b border-slate-700"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("hub", size="md").classes("text-blue-400")
                ui.label("ModueHarness Web Dashboard").classes("text-lg font-bold tracking-tight")
                ui.badge("v0.6.0", color="blue-600").classes("text-xs")

            with ui.row().classes("items-center gap-4"):
                projects = ctrl.get_projects()
                current_p = ctrl.project_name
                if current_p not in projects:
                    projects.append(current_p)

                ui.label("Project:").classes("text-sm text-slate-400")
                project_select = ui.select(
                    options=projects,
                    value=current_p,
                ).classes("w-44 bg-slate-800 text-white rounded")

                def on_project_change(e):
                    if e.value:
                        ctrl.switch_project(e.value)
                        ui.notify(f"Switched to project: {e.value}", type="info")
                        refresh_file_list()
                        refresh_artifacts()

                project_select.on_value_change(on_project_change)

                # Dark mode switch
                ui.button(icon="dark_mode", on_click=lambda: dark.toggle()).props("flat round text-color=white")

        # 2. Main 3-Column Layout
        with ui.row().classes("w-full h-[calc(100vh-60px)] p-3 gap-3 no-wrap"):
            # Left Pane: Command Dispatcher & Agent Settings
            with ui.card().classes("w-1/4 h-full flex flex-col justify-between p-4 bg-slate-800 border border-slate-700"):
                with ui.column().classes("w-full gap-3"):
                    ui.label("🎯 Task Dispatcher").classes("text-base font-semibold text-blue-300")
                    prompt_input = ui.textarea(
                        label="Natural Language Instruction",
                        placeholder="Enter what you want the AI team to implement...",
                    ).classes("w-full h-32")

                    with ui.row().classes("w-full gap-2 justify-between"):
                        run_btn = ui.button("Execute", icon="play_arrow", color="primary").classes("flex-1")
                        async_btn = ui.button("Background (&)", icon="schedule", color="secondary").classes("flex-1")
                        cancel_btn = ui.button(icon="stop", color="red").props("outline")

                    ui.separator().classes("my-2")
                    ui.label("⚙️ AI Team & Config").classes("text-sm font-semibold text-slate-300")

                    # Agents list
                    agents_container = ui.column().classes("w-full gap-1")

                    def refresh_agents():
                        agents_container.clear()
                        with agents_container:
                            for a in ctrl.get_agents_info():
                                with ui.row().classes("items-center justify-between w-full text-xs text-slate-300 p-1 bg-slate-900 rounded"):
                                    ui.label(f"• {a['name']} ({a['adapter']})").classes("font-mono")
                                    m = a.get("model") or "default"
                                    ui.label(f"{m}").classes("text-slate-400")

                    refresh_agents()

                with ui.column().classes("w-full gap-2 mt-auto"):
                    ui.label("⏱️ Timeout:").classes("text-xs text-slate-400")
                    t_label = ui.label("Unlimited" if ctrl.timeout is None else f"{ctrl.timeout}s").classes("text-xs font-mono text-green-400")

            # Center Pane: Real-time Live Stream & Stage
            with ui.card().classes("w-1/2 h-full flex flex-col p-4 bg-slate-800 border border-slate-700"):
                with ui.row().classes("w-full items-center justify-between border-b border-slate-700 pb-2"):
                    ui.label("💻 Real-time AI Stream").classes("text-base font-semibold text-green-400")
                    status_badge = ui.badge("Idle", color="slate").classes("text-xs")

                log_view = ui.log().classes("w-full flex-1 font-mono text-xs bg-slate-950 text-slate-200 p-3 rounded my-2")
                log_view.push("ModueHarness Ready. Enter a prompt to begin.")

                # Command execution logic
                async def run_task(is_async: bool = False):
                    cmd = prompt_input.value.strip()
                    if not cmd:
                        ui.notify("Please enter an instruction.", type="warning")
                        return

                    if is_async:
                        job = ctrl.execute_command_async(cmd)
                        log_view.push(f"\n[ASYNC] Background Job Started: {job.id}")
                        ui.notify(f"Background Job {job.id} dispatched", type="info")
                        refresh_jobs()
                    else:
                        status_badge.set_text("Executing...")
                        status_badge.props("color=amber-600")
                        log_view.push(f"\n>>> Executing: {cmd}")

                        def on_sync():
                            res = ctrl.execute_command(cmd)
                            return res

                        loop = asyncio.get_event_loop()
                        res = await loop.run_in_executor(None, on_sync)
                        status_badge.set_text("Completed" if res.get("success") else "Failed")
                        status_badge.props(f"color={'green-600' if res.get('success') else 'red-600'}")
                        log_view.push(f"\n<<< Finished with status: {res.get('status')} ({res.get('total_duration_sec', 0.0):.1f}s)")
                        if not res.get("success") and res.get("error"):
                            log_view.push(f"❌ Error: {res.get('error')}")
                        refresh_file_list()
                        refresh_artifacts()

                run_btn.on_click(lambda: run_task(is_async=False))
                async_btn.on_click(lambda: run_task(is_async=True))
                cancel_btn.on_click(lambda: (ctrl.cancel_job(), ui.notify("Task cancelled", type="warning")))

            # Right Pane: Blackboard Artifacts & Project Files
            with ui.card().classes("w-1/4 h-full flex flex-col p-4 bg-slate-800 border border-slate-700"):
                with ui.tabs().classes("w-full text-xs") as tabs:
                    tab_artifacts = ui.tab("Artifacts")
                    tab_files = ui.tab("Files")
                    tab_jobs = ui.tab("Jobs")

                with ui.tab_panels(tabs, value=tab_artifacts).classes("w-full flex-1 bg-transparent"):
                    # Tab 1: Artifacts
                    with ui.tab_panel(tab_artifacts).classes("p-0 flex flex-col gap-2"):
                        art_select = ui.select(options=[], label="Select Artifact").classes("w-full")
                        art_markdown = ui.markdown("No artifact selected.").classes("text-xs text-slate-300 overflow-auto flex-1")

                        def refresh_artifacts():
                            arts = [a["name"] for a in ctrl.get_artifacts()]
                            art_select.options = arts
                            if arts and not art_select.value:
                                art_select.value = arts[0]

                        art_select.on_value_change(lambda e: art_markdown.set_content(ctrl.get_artifact_content(e.value) if e.value else "Empty."))

                    # Tab 2: Project Files
                    with ui.tab_panel(tab_files).classes("p-0 flex flex-col gap-2"):
                        file_select = ui.select(options=[], label="Select Project File").classes("w-full")
                        file_code = ui.code("", language="python").classes("text-xs flex-1 overflow-auto")

                        def refresh_file_list():
                            files = ctrl.get_project_files()
                            file_select.options = files
                            if files and not file_select.value:
                                file_select.value = files[0]

                        file_select.on_value_change(lambda e: file_code.set_content(ctrl.get_project_file_content(e.value) if e.value else ""))

                    # Tab 3: Background Jobs
                    with ui.tab_panel(tab_jobs).classes("p-0 flex flex-col gap-2"):
                        jobs_container = ui.column().classes("w-full gap-2")

                        def refresh_jobs():
                            jobs_container.clear()
                            with jobs_container:
                                for j in ctrl.get_jobs():
                                    with ui.card().classes("w-full p-2 bg-slate-900 rounded text-xs"):
                                        ui.label(f"[{j['id']}] {j['status']} ({j['duration_sec']:.1f}s)").classes("font-bold")
                                        ui.label(j['command']).classes("text-slate-400 truncate")

        # Initial data population
        refresh_file_list()
        refresh_artifacts()
        refresh_jobs()

    # Prevent Starlette 404 from falling back to NiceGUI's internal run_script
    try:
        from starlette.responses import PlainTextResponse

        @app.exception_handler(404)
        async def _not_found_handler(request, exc):
            return PlainTextResponse("Not Found", status_code=404)
    except Exception:
        pass

    # Prepare ui.run kwargs
    run_kwargs = {
        "title": "ModueHarness Dashboard",
        "host": host,
        "port": port,
        "reload": False,
        "show": open_browser,
    }

    sig = inspect.signature(ui.run)
    if "root" in sig.parameters:
        run_kwargs["root"] = build_dashboard
    else:
        ui.page("/")(build_dashboard)

    ui.run(**run_kwargs)
