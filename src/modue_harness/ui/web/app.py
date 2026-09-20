"""NiceGUI Web UI Application implementation for ModueHarness."""

import asyncio
import inspect
from typing import Any, Dict, Optional
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

        # 2. Modals for AI Team Management
        current_edit_target = {"name": ""}

        # 2-A: Edit Agent Dialog
        edit_dialog = ui.dialog()
        with edit_dialog, ui.card().classes("w-96 p-4 bg-slate-900 border border-slate-700 text-white gap-2"):
            ui.label("⚙️ Configure AI Agent").classes("text-base font-bold text-blue-400")
            edit_name_label = ui.label("").classes("text-xs font-mono text-slate-400 mb-1")

            edit_adapter = ui.select(
                options=["claude", "agy", "aider", "generic"],
                label="Adapter Type",
            ).classes("w-full bg-slate-800 text-white rounded")

            edit_model = ui.input(
                label="Model Name",
                placeholder="e.g. sonnet, gemini-3.8-flash-high",
            ).classes("w-full")

            with ui.row().classes("gap-1 items-center"):
                ui.label("Presets:").classes("text-[11px] text-slate-400")
                ui.button("sonnet", on_click=lambda: edit_model.set_value("sonnet")).props("dense outline size=xs text-color=slate-300")
                ui.button("opus", on_click=lambda: edit_model.set_value("opus")).props("dense outline size=xs text-color=slate-300")
                ui.button("flash-high", on_click=lambda: edit_model.set_value("gemini-3.8-flash-high")).props("dense outline size=xs text-color=slate-300")
                ui.button("pro", on_click=lambda: edit_model.set_value("gemini-3.5-pro")).props("dense outline size=xs text-color=slate-300")

            edit_effort = ui.select(
                options=["default", "low", "medium", "high", "max", "off"],
                value="default",
                label="Reasoning Effort",
            ).classes("w-full bg-slate-800 text-white rounded")

            edit_leader_cb = ui.checkbox("Set as Team Leader (Conductor)").classes("text-xs text-slate-300")

            edit_instruction = ui.textarea(
                label="Custom Role / System Instruction (optional)",
                placeholder="e.g. You write clean, tested code matching specifications.",
            ).classes("w-full h-20 text-xs")

            def save_agent_edit():
                target_name = current_edit_target["name"]
                eff = None if edit_effort.value == "default" else edit_effort.value
                mod = edit_model.value.strip() or None
                ins = edit_instruction.value.strip() or None
                ctrl.update_agent(
                    name=target_name,
                    adapter_type=edit_adapter.value,
                    model=mod,
                    effort=eff,
                    is_conductor=edit_leader_cb.value,
                    system_instruction=ins,
                )
                ui.notify(f"Updated agent '{target_name}'", type="positive")
                edit_dialog.close()
                refresh_agents()

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=edit_dialog.close).props("flat text-color=slate-400")
                ui.button("Save", color="primary", on_click=save_agent_edit)

        def open_edit_dialog(agent_info: Dict[str, Any]):
            current_edit_target["name"] = agent_info["name"]
            edit_name_label.set_text(f"Agent: {agent_info['name']}")
            edit_adapter.set_value(agent_info["adapter"])
            edit_model.set_value(agent_info.get("model") or "")
            edit_effort.set_value(agent_info.get("effort") or "default")
            edit_leader_cb.set_value(agent_info["is_leader"])
            edit_instruction.set_value(agent_info.get("system_instruction") or "")
            edit_dialog.open()

        # 2-B: Add Agent Dialog
        add_dialog = ui.dialog()
        with add_dialog, ui.card().classes("w-96 p-4 bg-slate-900 border border-slate-700 text-white gap-2"):
            ui.label("➕ Add AI Team Member").classes("text-base font-bold text-green-400")
            add_name = ui.input(
                label="Agent Name",
                placeholder="e.g. tester, reviewer, architect",
            ).classes("w-full")

            add_adapter = ui.select(
                options=["claude", "agy", "aider", "generic"],
                value="claude",
                label="Adapter Type",
            ).classes("w-full bg-slate-800 text-white rounded")

            add_model = ui.input(
                label="Model (optional)",
                placeholder="e.g. sonnet, gemini-3.8-flash-high",
            ).classes("w-full")

            with ui.row().classes("gap-1 items-center"):
                ui.label("Presets:").classes("text-[11px] text-slate-400")
                ui.button("sonnet", on_click=lambda: add_model.set_value("sonnet")).props("dense outline size=xs text-color=slate-300")
                ui.button("flash-high", on_click=lambda: add_model.set_value("gemini-3.8-flash-high")).props("dense outline size=xs text-color=slate-300")

            add_effort = ui.select(
                options=["default", "low", "medium", "high", "max", "off"],
                value="default",
                label="Reasoning Effort",
            ).classes("w-full bg-slate-800 text-white rounded")

            add_leader_cb = ui.checkbox("Set as Team Leader (Conductor)").classes("text-xs text-slate-300")

            add_instruction = ui.textarea(
                label="Role / System Instruction (optional)",
                placeholder="e.g. You write unit tests and inspect code quality.",
            ).classes("w-full h-20 text-xs")

            def submit_new_agent():
                name = add_name.value.strip()
                if not name:
                    ui.notify("Please enter an agent name.", type="warning")
                    return
                eff = None if add_effort.value == "default" else add_effort.value
                mod = add_model.value.strip() or None
                ins = add_instruction.value.strip() or None
                ctrl.add_agent(
                    name=name,
                    adapter_type=add_adapter.value,
                    model=mod,
                    effort=eff,
                    is_conductor=add_leader_cb.value,
                    system_instruction=ins,
                )
                ui.notify(f"Added agent '{name}' ({add_adapter.value})", type="positive")
                add_name.set_value("")
                add_model.set_value("")
                add_instruction.set_value("")
                add_leader_cb.set_value(False)
                add_dialog.close()
                refresh_agents()

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=add_dialog.close).props("flat text-color=slate-400")
                ui.button("Add Agent", color="positive", on_click=submit_new_agent)

        def on_make_leader(name: str):
            if ctrl.set_conductor(name):
                ui.notify(f"'{name}' is now the Team Leader (Conductor)", type="positive")
                refresh_agents()

        def on_delete_agent(name: str):
            if ctrl.remove_agent(name):
                ui.notify(f"Removed agent '{name}'", type="info")
                refresh_agents()
            else:
                ui.notify("Cannot remove the last remaining agent.", type="warning")

        # 3. Main 3-Column Layout
        with ui.row().classes("w-full h-[calc(100vh-60px)] p-3 gap-3 no-wrap"):
            # Left Pane: Command Dispatcher & Agent Settings
            with ui.card().classes("w-1/4 h-full flex flex-col justify-between p-4 bg-slate-800 border border-slate-700 overflow-y-auto"):
                with ui.column().classes("w-full gap-3"):
                    # Task Dispatcher Card (clean spacing and no overlap)
                    with ui.card().classes("w-full p-3 bg-slate-900 border border-slate-700 rounded gap-2"):
                        ui.label("🎯 Task Dispatcher").classes("text-sm font-bold text-blue-300")
                        prompt_input = ui.textarea(
                            label="Natural Language Instruction",
                            placeholder="Enter what you want the AI team to implement...",
                        ).props("rows=3 outlined autogrow=false")\
                         .classes("w-full text-xs")

                        with ui.row().classes("w-full gap-2 justify-between items-center mt-1"):
                            run_btn = ui.button("Execute", icon="play_arrow", color="primary").props("dense").classes("flex-1 text-xs font-semibold")
                            async_btn = ui.button("Background (&)", icon="schedule", color="secondary").props("dense").classes("flex-1 text-xs font-semibold")
                            cancel_btn = ui.button(icon="stop", color="red").props("outline dense").tooltip("Cancel active task")

                    ui.separator().classes("my-1")

                    # AI Team Header
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label("⚙️ AI Team & Config").classes("text-sm font-semibold text-slate-300")
                        ui.button("+ Add AI", on_click=add_dialog.open).props("dense outline size=xs text-color=blue-400")

                    # Agents list container
                    agents_container = ui.column().classes("w-full gap-1.5")

                    def refresh_agents():
                        agents_container.clear()
                        agents = ctrl.get_agents_info()
                        with agents_container:
                            for a in agents:
                                with ui.card().classes("w-full p-2 bg-slate-900 border border-slate-700 rounded gap-1"):
                                    with ui.row().classes("items-center justify-between w-full no-wrap"):
                                        with ui.row().classes("items-center gap-1.5"):
                                            if a["is_leader"]:
                                                ui.badge("LEADER", color="amber-700").classes("text-[10px] font-bold")
                                            ui.label(a["name"]).classes("text-xs font-bold text-white font-mono")

                                        with ui.row().classes("items-center gap-0.5"):
                                            if not a["is_leader"]:
                                                ui.button(icon="star_border", on_click=lambda name=a["name"]: on_make_leader(name))\
                                                    .props("flat dense round size=xs text-color=amber-400")\
                                                    .tooltip("Set as Leader (Conductor)")

                                            ui.button(icon="edit", on_click=lambda agent=a: open_edit_dialog(agent))\
                                                .props("flat dense round size=xs text-color=blue-400")\
                                                .tooltip("Configure Agent")

                                            if len(agents) > 1:
                                                ui.button(icon="delete", on_click=lambda name=a["name"]: on_delete_agent(name))\
                                                    .props("flat dense round size=xs text-color=red-400")\
                                                    .tooltip("Remove Agent")

                                    with ui.row().classes("items-center justify-between w-full text-[11px] text-slate-400"):
                                        adapter_color = {
                                            "claude": "purple-600",
                                            "agy": "blue-600",
                                            "aider": "teal-600",
                                        }.get(a["adapter"], "slate-600")
                                        ui.badge(a["adapter"], color=adapter_color).classes("text-[10px]")

                                        m_text = a.get("model") or "default"
                                        e_text = f"/{a.get('effort')}" if a.get("effort") else ""
                                        ui.label(f"{m_text}{e_text}").classes("text-slate-400 font-mono truncate max-w-[120px]")

                    refresh_agents()

                # Timeout control
                with ui.column().classes("w-full gap-1 mt-auto pt-2 border-t border-slate-700"):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label("⏱️ Turn Timeout:").classes("text-xs text-slate-400 font-semibold")
                        t_label = ui.label("Unlimited" if ctrl.timeout is None else f"{ctrl.timeout}s").classes("text-xs font-mono text-green-400 font-bold")

                    with ui.row().classes("gap-1 w-full justify-between"):
                        def set_to(val):
                            ctrl.set_timeout(val)
                            t_label.set_text("Unlimited" if val is None else f"{val}s")
                            ui.notify(f"Timeout: {'Unlimited' if val is None else f'{val}s'}", type="info")

                        ui.button("Off", on_click=lambda: set_to(None)).props("dense outline size=xs text-color=slate-300").classes("flex-1")
                        ui.button("120s", on_click=lambda: set_to(120.0)).props("dense outline size=xs text-color=slate-300").classes("flex-1")
                        ui.button("300s", on_click=lambda: set_to(300.0)).props("dense outline size=xs text-color=slate-300").classes("flex-1")
                        ui.button("600s", on_click=lambda: set_to(600.0)).props("dense outline size=xs text-color=slate-300").classes("flex-1")

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
                        run_btn.props("loading")
                        run_btn.disable()
                        async_btn.disable()
                        status_badge.set_text("Executing...")
                        status_badge.props("color=amber-600")
                        log_view.push(f"\n>>> Executing: {cmd}")

                        try:
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
                        finally:
                            run_btn.props(remove="loading")
                            run_btn.enable()
                            async_btn.enable()

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

    try:
        ui.run(**run_kwargs)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
