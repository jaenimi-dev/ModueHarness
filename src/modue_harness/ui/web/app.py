"""NiceGUI Web UI Application implementation for ModueHarness."""

import asyncio
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional
from modue_harness.ui.controller import UIController
from modue_harness.ui.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, I18n


GLOBAL_VIEWPORT_CSS = """
<style>
    html, body {
        height: 100vh !important;
        max-height: 100vh !important;
        overflow: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .q-header {
        height: 52px !important;
    }
    .q-page-container {
        height: 100vh !important;
        max-height: 100vh !important;
        overflow: hidden !important;
        padding-top: 52px !important;
        padding-bottom: 0 !important;
    }
    .q-page {
        min-height: 0 !important;
        height: 100% !important;
        overflow: hidden !important;
        padding: 0 !important;
    }
</style>
"""


def run_app(
    controller: Optional[UIController] = None,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
    lang: str = DEFAULT_LANGUAGE,
) -> None:
    """Run NiceGUI dashboard application with multilingual support."""
    try:
        from nicegui import app, ui
    except ImportError as e:
        raise ImportError(
            "NiceGUI is not installed. Please install it using: pip install 'modue-harness[ui]' or pip install nicegui"
        ) from e

    # Inject global viewport reset CSS across all clients
    try:
        ui.add_head_html(GLOBAL_VIEWPORT_CSS, shared=True)
    except Exception:
        pass

    ctrl = controller or UIController(lang=lang)
    if hasattr(ctrl, "lang") and not ctrl.lang:
        ctrl.lang = lang

    def _build_dashboard_impl() -> None:
        # Dark mode by default
        dark = ui.dark_mode(value=True)

        current_lang = lang or getattr(ctrl, "lang", DEFAULT_LANGUAGE)
        i18n = I18n(current_lang)

        try:
            ui.add_head_html(GLOBAL_VIEWPORT_CSS)
        except Exception:
            pass

        # Persistent state for this client session across language switches
        state: Dict[str, Any] = {
            "prompt": "",
            "logs": [i18n("log_ready")],
            "is_running": False,
            "status_text_key": "status_idle",
            "status_color": "slate",
        }

        # Containers for layout
        header_container = ui.header().classes(
            "h-[52px] items-center justify-between bg-slate-900 text-white px-4 py-1 border-b border-slate-700"
        )
        main_container = ui.row().classes("w-full h-full p-2.5 gap-2.5 no-wrap box-border overflow-hidden")
        dialogs_container = ui.column().classes("hidden")

        # Forward declarations of handlers / variables
        prompt_input = None
        new_project_dialog = None
        on_refresh_all_click = lambda: None

        def _render_dashboard_impl() -> None:
            nonlocal prompt_input, new_project_dialog, on_refresh_all_click
            # Clear containers
            header_container.clear()
            main_container.clear()
            dialogs_container.clear()

            # 1. Header
            with header_container:
                with ui.row().classes("items-center gap-3"):
                    ui.icon("hub", size="md").classes("text-blue-400")
                    ui.label(i18n("app_title")).classes("text-lg font-bold tracking-tight")
                    ui.badge("v0.7.0", color="blue-600").classes("text-xs")

                with ui.row().classes("items-center gap-2 sm:gap-3"):
                    projects = ctrl.get_projects()
                    current_p = ctrl.project_name
                    if current_p and current_p not in projects:
                        projects.append(current_p)

                    ui.label(i18n("project")).classes("text-sm text-slate-400")
                    if projects:
                        project_select = ui.select(
                            options=projects,
                            value=current_p or projects[0],
                        ).classes("w-36 sm:w-44 bg-slate-800 text-white rounded text-xs")

                        def on_project_change(e):
                            if e.value and e.value in projects:
                                ctrl.switch_project(e.value)
                                bb_badge.set_text(f"blackboard/{e.value}")
                                ui.notify(i18n("switch_project_notify", name=e.value), type="info")
                                refresh_file_list()
                                refresh_artifacts()

                        project_select.on_value_change(on_project_change)
                    else:
                        project_select = ui.select(
                            options=[i18n("no_projects_yet")],
                            value=i18n("no_projects_yet"),
                        ).props("disable").classes("w-36 sm:w-44 bg-slate-800 text-slate-400 rounded text-xs")

                    def refresh_projects():
                        try:
                            projs = ctrl.get_projects()
                            cur = ctrl.project_name
                            if cur and cur not in projs:
                                projs.append(cur)
                            if projs:
                                project_select.options = projs
                                if cur in projs:
                                    project_select.value = cur
                                elif not project_select.value or project_select.value not in projs:
                                    project_select.value = projs[0]
                                project_select.enable()
                            else:
                                project_select.options = [i18n("no_projects_yet")]
                                project_select.value = i18n("no_projects_yet")
                                project_select.disable()
                        except Exception:
                            pass

                    # + New Project button
                    ui.button(
                        i18n("btn_new_project"),
                        on_click=lambda: new_project_dialog.open() if new_project_dialog else None,
                    ).props("dense outline size=xs text-color=blue-300")\
                     .tooltip(i18n("tooltip_new_project"))\
                     .classes("text-xs border-blue-500/50 hover:bg-blue-900/30")

                    # Refresh all button in header
                    ui.button(
                        icon="refresh",
                        on_click=lambda: on_refresh_all_click(),
                    ).props("dense outline size=xs text-color=slate-300")\
                     .tooltip(i18n("tooltip_refresh_all"))\
                     .classes("text-xs border-slate-600 hover:bg-slate-800")

                    bb_text = f"blackboard/{current_p}" if current_p else "blackboard"
                    bb_badge = ui.badge(bb_text, color="slate-700").classes("text-[10px] font-mono text-slate-400 hidden sm:inline-flex")

                    # Language Selector
                    lang_select = ui.select(
                        options=SUPPORTED_LANGUAGES,
                        value=i18n.lang,
                    ).props("dense outlined").classes("w-28 sm:w-32 bg-slate-800 text-white rounded text-xs")

                    def on_lang_change(e):
                        if e.value and e.value != i18n.lang:
                            if prompt_input:
                                state["prompt"] = prompt_input.value
                            i18n.lang = e.value
                            ctrl.lang = e.value
                            render_dashboard()

                    lang_select.on_value_change(on_lang_change)

                    # Dark mode switch
                    ui.button(icon="dark_mode", on_click=lambda: dark.toggle())\
                        .props("flat round text-color=white")\
                        .tooltip(i18n("theme_toggle"))

            # 2. Modals (inside dialogs_container)
            current_edit_target = {"name": ""}

            with dialogs_container:
                # 2-0: New Project Dialog
                new_project_dialog = ui.dialog()
                with new_project_dialog, ui.card().classes("w-96 p-4 bg-slate-900 border border-slate-700 text-white gap-2"):
                    ui.label(i18n("dialog_new_project_title")).classes("text-base font-bold text-blue-400")
                    new_proj_input = ui.input(
                        label=i18n("project_name_label"),
                        placeholder=i18n("project_name_placeholder"),
                    ).classes("w-full")

                    def create_project_submit():
                        name = new_proj_input.value.strip()
                        if not name or any(c in r'\/:*?"<>|' for c in name):
                            ui.notify(i18n("notify_invalid_project_name"), type="warning")
                            return
                        ctrl.switch_project(name)
                        new_proj_input.set_value("")
                        new_project_dialog.close()
                        ui.notify(i18n("notify_project_created", name=name), type="positive")
                        render_dashboard()

                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        ui.button(i18n("btn_cancel"), on_click=new_project_dialog.close).props("flat text-color=slate-400")
                        ui.button(i18n("btn_create_project"), color="primary", on_click=create_project_submit)

                # 2-A: Edit Agent Dialog
                edit_dialog = ui.dialog()
                with edit_dialog, ui.card().classes("w-96 p-4 bg-slate-900 border border-slate-700 text-white gap-2"):
                    ui.label(i18n("dialog_edit_title")).classes("text-base font-bold text-blue-400")
                    edit_name_label = ui.label("").classes("text-xs font-mono text-slate-400 mb-1")

                    edit_adapter = ui.select(
                        options=["claude", "agy", "aider", "generic"],
                        label=i18n("adapter_type"),
                    ).classes("w-full bg-slate-800 text-white rounded")

                    edit_model = ui.input(
                        label=i18n("model_name"),
                        placeholder=i18n("model_placeholder"),
                    ).classes("w-full")

                    with ui.row().classes("gap-1 items-center"):
                        ui.label(i18n("presets")).classes("text-[11px] text-slate-400")
                        ui.button("sonnet", on_click=lambda: edit_model.set_value("sonnet")).props("dense outline size=xs text-color=slate-300")
                        ui.button("opus", on_click=lambda: edit_model.set_value("opus")).props("dense outline size=xs text-color=slate-300")
                        ui.button("flash-high", on_click=lambda: edit_model.set_value("gemini-3.8-flash-high")).props("dense outline size=xs text-color=slate-300")
                        ui.button("pro", on_click=lambda: edit_model.set_value("gemini-3.5-pro")).props("dense outline size=xs text-color=slate-300")

                    edit_effort = ui.select(
                        options=["default", "low", "medium", "high", "max", "off"],
                        value="default",
                        label=i18n("reasoning_effort"),
                    ).classes("w-full bg-slate-800 text-white rounded")

                    edit_leader_cb = ui.checkbox(i18n("set_as_leader")).classes("text-xs text-slate-300")

                    edit_instruction = ui.textarea(
                        label=i18n("custom_instruction"),
                        placeholder=i18n("instruction_placeholder_edit"),
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
                        ui.notify(
                            i18n("notify_agent_saved_to", name=target_name, path=ctrl.config_file_name),
                            type="positive",
                        )
                        edit_dialog.close()
                        refresh_agents()

                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        ui.button(i18n("btn_cancel"), on_click=edit_dialog.close).props("flat text-color=slate-400")
                        ui.button(i18n("btn_save"), color="primary", on_click=save_agent_edit)

                def open_edit_dialog(agent_info: Dict[str, Any]):
                    current_edit_target["name"] = agent_info["name"]
                    edit_name_label.set_text(i18n("agent_name_label", name=agent_info["name"]))
                    edit_adapter.set_value(agent_info["adapter"])
                    edit_model.set_value(agent_info.get("model") or "")
                    edit_effort.set_value(agent_info.get("effort") or "default")
                    edit_leader_cb.set_value(agent_info["is_leader"])
                    edit_instruction.set_value(agent_info.get("system_instruction") or "")
                    edit_dialog.open()

                # 2-B: Add Agent Dialog
                add_dialog = ui.dialog()
                with add_dialog, ui.card().classes("w-96 p-4 bg-slate-900 border border-slate-700 text-white gap-2"):
                    ui.label(i18n("dialog_add_title")).classes("text-base font-bold text-green-400")
                    add_name = ui.input(
                        label=i18n("agent_name"),
                        placeholder=i18n("agent_name_placeholder"),
                    ).classes("w-full")

                    add_adapter = ui.select(
                        options=["claude", "agy", "aider", "generic"],
                        value="claude",
                        label=i18n("adapter_type"),
                    ).classes("w-full bg-slate-800 text-white rounded")

                    add_model = ui.input(
                        label=i18n("model_optional"),
                        placeholder=i18n("model_placeholder"),
                    ).classes("w-full")

                    with ui.row().classes("gap-1 items-center"):
                        ui.label(i18n("presets")).classes("text-[11px] text-slate-400")
                        ui.button("sonnet", on_click=lambda: add_model.set_value("sonnet")).props("dense outline size=xs text-color=slate-300")
                        ui.button("flash-high", on_click=lambda: add_model.set_value("gemini-3.8-flash-high")).props("dense outline size=xs text-color=slate-300")

                    add_effort = ui.select(
                        options=["default", "low", "medium", "high", "max", "off"],
                        value="default",
                        label=i18n("reasoning_effort"),
                    ).classes("w-full bg-slate-800 text-white rounded")

                    add_leader_cb = ui.checkbox(i18n("set_as_leader")).classes("text-xs text-slate-300")

                    add_instruction = ui.textarea(
                        label=i18n("custom_instruction"),
                        placeholder=i18n("instruction_placeholder_add"),
                    ).classes("w-full h-20 text-xs")

                    def submit_new_agent():
                        name = add_name.value.strip()
                        if not name:
                            ui.notify(i18n("notify_enter_agent_name"), type="warning")
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
                        ui.notify(
                            i18n("notify_agent_saved_to", name=name, path=ctrl.config_file_name),
                            type="positive",
                        )
                        add_name.set_value("")
                        add_model.set_value("")
                        add_instruction.set_value("")
                        add_leader_cb.set_value(False)
                        add_dialog.close()
                        refresh_agents()

                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        ui.button(i18n("btn_cancel"), on_click=add_dialog.close).props("flat text-color=slate-400")
                        ui.button(i18n("btn_add_agent"), color="positive", on_click=submit_new_agent)

            def on_make_leader(name: str):
                if ctrl.set_conductor(name):
                    ui.notify(
                        i18n("notify_leader_set", name=name) + f" ({ctrl.config_file_name})",
                        type="positive",
                    )
                    refresh_agents()

            def on_delete_agent(name: str):
                if ctrl.remove_agent(name):
                    ui.notify(
                        i18n("notify_agent_removed", name=name) + f" ({ctrl.config_file_name})",
                        type="info",
                    )
                    refresh_agents()
                else:
                    ui.notify(i18n("notify_cannot_remove_last"), type="warning")

            # 3. Main 3-Column Layout (fits 100vh with no outer scrollbars)
            with main_container:
                # Left Pane: Command Dispatcher & Agent Settings
                with ui.card().classes(
                    "w-1/4 h-full flex flex-col p-3 bg-slate-800 border border-slate-700 rounded-lg overflow-hidden box-border"
                ):
                    # Task Dispatcher Card (Compact, fixed height)
                    with ui.card().classes("w-full p-2.5 bg-slate-900 border border-slate-700 rounded gap-1.5 flex-shrink-0"):
                        ui.label(i18n("task_dispatcher")).classes("text-sm font-bold text-blue-300")
                        prompt_input = ui.textarea(
                            label=i18n("prompt_label"),
                            placeholder=i18n("prompt_placeholder"),
                            value=state["prompt"],
                        ).props("rows=2 outlined autogrow=false")\
                         .classes("w-full text-xs")

                        prompt_input.on_value_change(lambda e: state.update({"prompt": e.value}))

                        with ui.row().classes("w-full gap-1.5 justify-between items-center mt-1 flex-shrink-0"):
                            run_btn = ui.button(i18n("btn_execute"), icon="play_arrow", color="primary")\
                                .props("dense").classes("flex-1 text-xs font-semibold")
                            async_btn = ui.button(i18n("btn_background"), icon="schedule", color="secondary")\
                                .props("dense").classes("flex-1 text-xs font-semibold")
                            cancel_btn = ui.button(icon="stop", color="red")\
                                .props("outline dense").tooltip(i18n("tooltip_cancel"))

                            if state["is_running"]:
                                run_btn.props("loading")
                                run_btn.disable()
                                async_btn.disable()

                    ui.separator().classes("my-1 flex-shrink-0")

                    # AI Team Header with config file badge
                    with ui.row().classes("items-center justify-between w-full flex-shrink-0 mb-1"):
                        with ui.row().classes("items-center gap-1.5"):
                            ui.label(i18n("ai_team_config")).classes("text-xs font-semibold text-slate-300")
                            ui.badge(ctrl.config_file_name, color="slate-700").classes("text-[9px] font-mono text-slate-400")
                        ui.button(i18n("btn_add_ai"), on_click=add_dialog.open).props("dense outline size=xs text-color=blue-400")

                    # Agents list container (Scrolls independently within left pane!)
                    agents_container = ui.column().classes("w-full flex-1 min-h-0 overflow-y-auto gap-1.5 pr-0.5")

                    def refresh_agents():
                        agents_container.clear()
                        agents = ctrl.get_agents_info()
                        with agents_container:
                            for a in agents:
                                with ui.card().classes("w-full p-2 bg-slate-900 border border-slate-700 rounded gap-1 flex-shrink-0"):
                                    with ui.row().classes("items-center justify-between w-full no-wrap"):
                                        with ui.row().classes("items-center gap-1.5"):
                                            if a["is_leader"]:
                                                ui.badge(i18n("badge_leader"), color="amber-700").classes("text-[10px] font-bold")
                                            ui.label(a["name"]).classes("text-xs font-bold text-white font-mono")

                                        with ui.row().classes("items-center gap-0.5"):
                                            if not a["is_leader"]:
                                                ui.button(icon="star_border", on_click=lambda name=a["name"]: on_make_leader(name))\
                                                    .props("flat dense round size=xs text-color=amber-400")\
                                                    .tooltip(i18n("tooltip_make_leader"))

                                            ui.button(icon="edit", on_click=lambda agent=a: open_edit_dialog(agent))\
                                                .props("flat dense round size=xs text-color=blue-400")\
                                                .tooltip(i18n("tooltip_configure_agent"))

                                            if len(agents) > 1:
                                                ui.button(icon="delete", on_click=lambda name=a["name"]: on_delete_agent(name))\
                                                    .props("flat dense round size=xs text-color=red-400")\
                                                    .tooltip(i18n("tooltip_remove_agent"))

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

                    # Timeout control (Always pinned at the bottom, never clipped!)
                    with ui.column().classes("w-full gap-1 mt-auto pt-2 border-t border-slate-700 flex-shrink-0"):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label(i18n("turn_timeout")).classes("text-xs text-slate-400 font-semibold")
                            t_val_str = i18n("unlimited") if ctrl.timeout is None else f"{ctrl.timeout}s"
                            t_label = ui.label(t_val_str).classes("text-xs font-mono text-green-400 font-bold")

                        with ui.row().classes("gap-1 w-full justify-between"):
                            def set_to(val):
                                ctrl.set_timeout(val)
                                t_str = i18n("unlimited") if val is None else f"{val}s"
                                t_label.set_text(t_str)
                                ui.notify(i18n("notify_timeout_set", val=t_str), type="info")

                            ui.button(i18n("timeout_off"), on_click=lambda: set_to(None)).props("dense outline size=xs text-color=slate-300").classes("flex-1")
                            ui.button("120s", on_click=lambda: set_to(120.0)).props("dense outline size=xs text-color=slate-300").classes("flex-1")
                            ui.button("300s", on_click=lambda: set_to(300.0)).props("dense outline size=xs text-color=slate-300").classes("flex-1")
                            ui.button("600s", on_click=lambda: set_to(600.0)).props("dense outline size=xs text-color=slate-300").classes("flex-1")

                # Center Pane: Real-time Live Stream & Stage
                with ui.card().classes(
                    "w-1/2 h-full flex flex-col p-3 bg-slate-800 border border-slate-700 rounded-lg overflow-hidden box-border"
                ):
                    with ui.row().classes("w-full items-center justify-between border-b border-slate-700 pb-2 flex-shrink-0"):
                        ui.label(i18n("realtime_stream")).classes("text-base font-semibold text-green-400")
                        status_badge = ui.badge(i18n(state["status_text_key"]), color=state["status_color"]).classes("text-xs")

                    log_view = ui.log().classes(
                        "w-full flex-1 min-h-0 font-mono text-xs bg-slate-950 text-slate-200 p-2.5 rounded my-1.5 overflow-auto"
                    )
                    for line in state["logs"]:
                        log_view.push(line)

                    def push_log(text: str):
                        state["logs"].append(text)
                        log_view.push(text)

                    # Command execution logic
                    async def run_task(is_async: bool = False):
                        cmd = prompt_input.value.strip() if prompt_input else ""
                        if not cmd:
                            ui.notify(i18n("notify_enter_instruction"), type="warning")
                            return

                        if not ctrl.project_name:
                            ui.notify(i18n("notify_select_project_first"), type="warning")
                            if new_project_dialog:
                                new_project_dialog.open()
                            return

                        if is_async:
                            job = ctrl.execute_command_async(cmd)
                            push_log(i18n("log_bg_job_started", id=job.id))
                            ui.notify(i18n("notify_bg_job_dispatched", id=job.id), type="info")
                            refresh_jobs()
                        else:
                            state["is_running"] = True
                            state["status_text_key"] = "status_executing"
                            state["status_color"] = "amber-600"
                            run_btn.props("loading")
                            run_btn.disable()
                            async_btn.disable()
                            status_badge.set_text(i18n("status_executing"))
                            status_badge.props("color=amber-600")
                            push_log(i18n("log_executing", cmd=cmd))

                            try:
                                def on_sync():
                                    return ctrl.execute_command(cmd)

                                loop = asyncio.get_event_loop()
                                res = await loop.run_in_executor(None, on_sync)
                                success = res.get("success", False)
                                state["status_text_key"] = "status_completed" if success else "status_failed"
                                state["status_color"] = "green-600" if success else "red-600"
                                status_badge.set_text(i18n(state["status_text_key"]))
                                status_badge.props(f"color={state['status_color']}")
                                push_log(
                                    i18n(
                                        "log_finished",
                                        status=res.get("status"),
                                        duration=res.get("total_duration_sec", 0.0),
                                    )
                                )
                                if not success and res.get("error"):
                                    push_log(i18n("log_error", error=res.get("error")))
                                refresh_file_list()
                                refresh_artifacts()
                            finally:
                                state["is_running"] = False
                                run_btn.props(remove="loading")
                                run_btn.enable()
                                async_btn.enable()

                    run_btn.on_click(lambda: run_task(is_async=False))
                    async_btn.on_click(lambda: run_task(is_async=True))
                    cancel_btn.on_click(lambda: (ctrl.cancel_job(), ui.notify(i18n("notify_task_cancelled"), type="warning")))

                # Right Pane: Blackboard Artifacts & Project Files
                with ui.card().classes(
                    "w-1/4 h-full flex flex-col p-3 bg-slate-800 border border-slate-700 rounded-lg overflow-hidden box-border"
                ):
                    with ui.row().classes("w-full items-center justify-between border-b border-slate-700 pb-1 flex-shrink-0"):
                        with ui.tabs().classes("text-xs flex-1") as tabs:
                            tab_artifacts = ui.tab(i18n("tab_artifacts"))
                            tab_files = ui.tab(i18n("tab_files"))
                            tab_jobs = ui.tab(i18n("tab_jobs"))
                        ui.button(icon="refresh", on_click=lambda: on_refresh_all_click())\
                            .props("flat dense round size=sm text-color=slate-300 hover:text-white")\
                            .tooltip(i18n("tooltip_refresh_all"))

                    with ui.tab_panels(tabs, value=tab_artifacts).classes("w-full flex-1 min-h-0 bg-transparent overflow-hidden"):
                        # Tab 1: Artifacts (Project-isolated)
                        with ui.tab_panel(tab_artifacts).classes("p-0 h-full flex flex-col gap-2 overflow-hidden"):
                            with ui.row().classes("w-full items-center gap-1.5 flex-shrink-0"):
                                art_select = ui.select(options=[], label=i18n("select_artifact")).classes("flex-1 min-w-0 text-xs")
                                ui.button(icon="refresh", on_click=lambda: on_refresh_artifacts_click())\
                                    .props("dense outline size=sm text-color=blue-300")\
                                    .tooltip(i18n("tooltip_refresh_artifacts"))\
                                    .classes("border-blue-500/40 hover:bg-blue-900/30")

                            art_markdown = ui.markdown(i18n("no_artifact_selected")).classes(
                                "text-xs text-slate-300 overflow-auto flex-1 min-h-0 p-2 bg-slate-900/50 rounded border border-slate-700/50"
                            )

                            def refresh_artifacts():
                                try:
                                    arts = [a["name"] for a in ctrl.get_artifacts()]
                                    art_select.options = arts
                                    if arts:
                                        chosen = art_select.value if art_select.value in arts else arts[0]
                                        art_select.value = chosen
                                        content = ctrl.get_artifact_content(chosen)
                                        art_markdown.set_content(content if content else i18n("empty_content"))
                                    else:
                                        art_select.value = None
                                        art_markdown.set_content(i18n("no_artifact_selected"))
                                except Exception as ex:
                                    art_select.options = []
                                    art_select.value = None
                                    art_markdown.set_content(i18n("no_artifact_selected"))

                            art_select.on_value_change(
                                lambda e: art_markdown.set_content(
                                    ctrl.get_artifact_content(e.value) if e.value else i18n("no_artifact_selected")
                                )
                            )

                        # Tab 2: Project Files
                        with ui.tab_panel(tab_files).classes("p-0 h-full flex flex-col gap-2 overflow-hidden"):
                            with ui.row().classes("w-full items-center gap-1.5 flex-shrink-0"):
                                file_select = ui.select(options=[], label=i18n("select_file")).classes("flex-1 min-w-0 text-xs")
                                ui.button(icon="refresh", on_click=lambda: on_refresh_files_click())\
                                    .props("dense outline size=sm text-color=blue-300")\
                                    .tooltip(i18n("tooltip_refresh_files"))\
                                    .classes("border-blue-500/40 hover:bg-blue-900/30")

                            file_code = ui.code("", language="python").classes("text-xs flex-1 min-h-0 overflow-auto rounded")

                            def refresh_file_list():
                                try:
                                    files = ctrl.get_project_files()
                                    file_select.options = files
                                    if files:
                                        chosen = file_select.value if file_select.value in files else files[0]
                                        file_select.value = chosen
                                        file_code.set_content(ctrl.get_project_file_content(chosen))
                                    else:
                                        file_select.value = None
                                        file_code.set_content("")
                                except Exception as ex:
                                    file_select.options = []
                                    file_select.value = None
                                    file_code.set_content("")

                            file_select.on_value_change(
                                lambda e: file_code.set_content(
                                    ctrl.get_project_file_content(e.value) if e.value else ""
                                )
                            )

                        # Tab 3: Background Jobs
                        with ui.tab_panel(tab_jobs).classes("p-0 h-full flex flex-col gap-2 overflow-hidden"):
                            jobs_container = ui.column().classes("w-full flex-1 min-h-0 overflow-y-auto gap-2")

                            def refresh_jobs():
                                try:
                                    jobs_container.clear()
                                    with jobs_container:
                                        jobs = ctrl.get_jobs()
                                        if not jobs:
                                            ui.label(i18n("empty_content")).classes("text-xs text-slate-400 italic p-2")
                                        for j in jobs:
                                            with ui.card().classes("w-full p-2 bg-slate-900 rounded text-xs"):
                                                ui.label(f"[{j['id']}] {j['status']} ({j['duration_sec']:.1f}s)").classes("font-bold")
                                                ui.label(j['command']).classes("text-slate-400 truncate")
                                except Exception:
                                    pass

                    def on_refresh_artifacts_click():
                        refresh_artifacts()
                        ui.notify(i18n("notify_artifacts_refreshed"), type="info")

                    def on_refresh_files_click():
                        refresh_file_list()
                        ui.notify(i18n("notify_files_refreshed"), type="info")

                    def on_refresh_all_click_impl():
                        refresh_projects()
                        refresh_artifacts()
                        refresh_file_list()
                        refresh_jobs()
                        ui.notify(i18n("notify_refreshed"), type="info")

                    on_refresh_all_click = on_refresh_all_click_impl

                # Initial data population
                try:
                    refresh_file_list()
                except Exception:
                    pass
                try:
                    refresh_artifacts()
                except Exception:
                    pass
                try:
                    refresh_jobs()
                except Exception:
                    pass

        def render_dashboard() -> None:
            try:
                _render_dashboard_impl()
            except Exception as exc:
                import sys, traceback
                traceback.print_exc(file=sys.stderr)
                try:
                    main_container.clear()
                    with main_container:
                        with ui.card().classes("w-full p-6 bg-slate-900 border border-red-500 rounded text-white"):
                            ui.label("⚠️ ModueHarness Dashboard Render Error").classes("text-lg font-bold text-red-400")
                            ui.label(str(exc)).classes("text-sm text-slate-300 my-2")
                            ui.code(traceback.format_exc(), language="text").classes("text-xs bg-slate-950 p-3 rounded overflow-auto")
                except Exception:
                    pass

        # Initial render of the dashboard
        render_dashboard()

    def build_dashboard() -> None:
        """Construct the 3-column dashboard UI layout for each connecting client."""
        try:
            _build_dashboard_impl()
        except Exception as exc:
            import sys, traceback
            traceback.print_exc(file=sys.stderr)
            try:
                with ui.card().classes("w-full max-w-3xl mx-auto my-10 p-6 bg-slate-900 border border-red-500 rounded text-white"):
                    ui.label("⚠️ ModueHarness Dashboard Error").classes("text-lg font-bold text-red-400")
                    ui.label(str(exc)).classes("text-sm text-slate-300 my-2")
                    ui.code(traceback.format_exc(), language="text").classes("text-xs bg-slate-950 p-3 rounded overflow-auto")
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

    # Always register root route "/" with ui.page for standard FastAPI/Starlette routing
    try:
        ui.page("/")(build_dashboard)
    except Exception:
        pass

    sig = inspect.signature(ui.run)
    if "root" in sig.parameters:
        run_kwargs["root"] = build_dashboard

    try:
        ui.run(**run_kwargs)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
