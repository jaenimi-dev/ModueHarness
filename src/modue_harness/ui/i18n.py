"""Internationalization (i18n) module for ModueHarness Web UI and CLI."""

from typing import Any, Dict, Optional

SUPPORTED_LANGUAGES: Dict[str, str] = {
    "ko": "🇰🇷 한국어",
    "en": "🇺🇸 English",
}

DEFAULT_LANGUAGE: str = "ko"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ko": {
        # App / Header
        "app_title": "ModueHarness 웹 대시보드",
        "project": "프로젝트:",
        "switch_project_notify": "프로젝트가 변경되었습니다: {name}",
        "language": "언어",
        "theme_toggle": "다크 모드 전환",

        # Left Pane - Task Dispatcher
        "task_dispatcher": "🎯 작업 지시",
        "prompt_label": "자연어 작업 지시",
        "prompt_placeholder": "AI 팀이 구현할 작업 내용을 입력하세요...",
        "btn_execute": "실행",
        "btn_background": "백그라운드 (&)",
        "tooltip_cancel": "현재 실행 중인 작업 취소",

        # Left Pane - AI Team & Config
        "ai_team_config": "⚙️ AI 팀 및 환경 설정",
        "btn_add_ai": "+ AI 추가",
        "badge_leader": "LEADER",
        "tooltip_make_leader": "팀장(지휘관)으로 지정",
        "tooltip_configure_agent": "에이전트 설정",
        "tooltip_remove_agent": "에이전트 삭제",
        "notify_leader_set": "'{name}'이(가) 팀장(지휘관)으로 지정되었습니다.",
        "notify_agent_removed": "에이전트 '{name}'이(가) 삭제되었습니다.",
        "notify_cannot_remove_last": "마지막 남은 에이전트는 삭제할 수 없습니다.",

        # Left Pane - Turn Timeout
        "turn_timeout": "⏱️ 턴 제한시간:",
        "unlimited": "무제한",
        "timeout_off": "해제",
        "notify_timeout_set": "제한시간: {val}",

        # Center Pane - Stream
        "realtime_stream": "💻 실시간 AI 스트림",
        "status_idle": "대기 중",
        "status_executing": "실행 중...",
        "status_completed": "완료됨",
        "status_failed": "실패",
        "log_ready": "ModueHarness 준비 완료. 프롬프트를 입력하여 작업을 시작하세요.",
        "notify_enter_instruction": "작업 지시 내용을 입력해주세요.",
        "notify_bg_job_dispatched": "백그라운드 작업 {id}이(가) 시작되었습니다.",
        "log_bg_job_started": "\n[ASYNC] 백그라운드 작업 시작: {id}",
        "log_executing": "\n>>> 작업 실행 중: {cmd}",
        "log_finished": "\n<<< 작업 완료 (상태: {status}, 소요 시간: {duration:.1f}초)",
        "log_error": "❌ 오류: {error}",
        "notify_task_cancelled": "작업이 취소되었습니다.",

        # Right Pane - Tabs & Content
        "tab_artifacts": "산출물 (Artifacts)",
        "tab_files": "프로젝트 파일",
        "tab_jobs": "작업 이력 (Jobs)",
        "select_artifact": "산출물 선택",
        "no_artifact_selected": "선택된 산출물이 없습니다.",
        "select_file": "프로젝트 파일 선택",
        "empty_content": "내용 없음",

        # Dialogs - Edit Agent
        "dialog_edit_title": "⚙️ AI 에이전트 설정",
        "agent_name_label": "에이전트: {name}",
        "adapter_type": "어댑터 종류",
        "model_name": "모델명",
        "model_placeholder": "예: sonnet, gemini-3.8-flash-high",
        "presets": "프리셋:",
        "reasoning_effort": "추론 강도 (Reasoning Effort)",
        "set_as_leader": "팀장(지휘관)으로 지정",
        "custom_instruction": "역할 및 시스템 지시문 (선택사항)",
        "instruction_placeholder_edit": "예: 요구사항에 맞춰 테스트 코드를 작성하고 코드 품질을 검사합니다.",
        "btn_cancel": "취소",
        "btn_save": "저장",
        "notify_agent_updated": "에이전트 '{name}' 설정이 저장되었습니다.",
        "notify_agent_saved_to": "에이전트 '{name}' 설정이 {path}에 저장되었습니다.",

        # Dialogs - Add Agent
        "dialog_add_title": "➕ AI 팀 멤버 추가",
        "agent_name": "에이전트 이름",
        "agent_name_placeholder": "예: tester, reviewer, architect",
        "model_optional": "모델명 (선택사항)",
        "instruction_placeholder_add": "예: 단위 테스트를 작성하고 코드 품질을 검사합니다.",
        "btn_add_agent": "에이전트 추가",
        "notify_enter_agent_name": "에이전트 이름을 입력하세요.",
        "notify_agent_added": "에이전트 '{name}'({adapter})이(가) 추가되었습니다.",
    },
    "en": {
        # App / Header
        "app_title": "ModueHarness Web Dashboard",
        "project": "Project:",
        "switch_project_notify": "Switched to project: {name}",
        "language": "Language",
        "theme_toggle": "Toggle dark mode",

        # Left Pane - Task Dispatcher
        "task_dispatcher": "🎯 Task Dispatcher",
        "prompt_label": "Natural Language Instruction",
        "prompt_placeholder": "Enter what you want the AI team to implement...",
        "btn_execute": "Execute",
        "btn_background": "Background (&)",
        "tooltip_cancel": "Cancel active task",

        # Left Pane - AI Team & Config
        "ai_team_config": "⚙️ AI Team & Config",
        "btn_add_ai": "+ Add AI",
        "badge_leader": "LEADER",
        "tooltip_make_leader": "Set as Leader (Conductor)",
        "tooltip_configure_agent": "Configure Agent",
        "tooltip_remove_agent": "Remove Agent",
        "notify_leader_set": "'{name}' is now the Team Leader (Conductor)",
        "notify_agent_removed": "Removed agent '{name}'",
        "notify_cannot_remove_last": "Cannot remove the last remaining agent.",

        # Left Pane - Turn Timeout
        "turn_timeout": "⏱️ Turn Timeout:",
        "unlimited": "Unlimited",
        "timeout_off": "Off",
        "notify_timeout_set": "Timeout: {val}",

        # Center Pane - Stream
        "realtime_stream": "💻 Real-time AI Stream",
        "status_idle": "Idle",
        "status_executing": "Executing...",
        "status_completed": "Completed",
        "status_failed": "Failed",
        "log_ready": "ModueHarness Ready. Enter a prompt to begin.",
        "notify_enter_instruction": "Please enter an instruction.",
        "notify_bg_job_dispatched": "Background Job {id} dispatched",
        "log_bg_job_started": "\n[ASYNC] Background Job Started: {id}",
        "log_executing": "\n>>> Executing: {cmd}",
        "log_finished": "\n<<< Finished with status: {status} ({duration:.1f}s)",
        "log_error": "❌ Error: {error}",
        "notify_task_cancelled": "Task cancelled",

        # Right Pane - Tabs & Content
        "tab_artifacts": "Artifacts",
        "tab_files": "Files",
        "tab_jobs": "Jobs",
        "select_artifact": "Select Artifact",
        "no_artifact_selected": "No artifact selected.",
        "select_file": "Select Project File",
        "empty_content": "Empty.",

        # Dialogs - Edit Agent
        "dialog_edit_title": "⚙️ Configure AI Agent",
        "agent_name_label": "Agent: {name}",
        "adapter_type": "Adapter Type",
        "model_name": "Model Name",
        "model_placeholder": "e.g. sonnet, gemini-3.8-flash-high",
        "presets": "Presets:",
        "reasoning_effort": "Reasoning Effort",
        "set_as_leader": "Set as Team Leader (Conductor)",
        "custom_instruction": "Custom Role / System Instruction (optional)",
        "instruction_placeholder_edit": "e.g. You write clean, tested code matching specifications.",
        "btn_cancel": "Cancel",
        "btn_save": "Save",
        "notify_agent_updated": "Updated agent '{name}'",
        "notify_agent_saved_to": "Agent '{name}' configuration saved to {path}.",

        # Dialogs - Add Agent
        "dialog_add_title": "➕ Add AI Team Member",
        "agent_name": "Agent Name",
        "agent_name_placeholder": "e.g. tester, reviewer, architect",
        "model_optional": "Model (optional)",
        "instruction_placeholder_add": "e.g. You write unit tests and inspect code quality.",
        "btn_add_agent": "Add Agent",
        "notify_enter_agent_name": "Please enter an agent name.",
        "notify_agent_added": "Added agent '{name}' ({adapter})",
    },
}


def get_text(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs: Any) -> str:
    """Retrieve translated text by key and language code with optional formatting."""
    lang_dict = TRANSLATIONS.get(lang) or TRANSLATIONS.get(DEFAULT_LANGUAGE, {})
    text = lang_dict.get(key)
    if text is None:
        # Fallback to English, then key itself
        text = TRANSLATIONS.get("en", {}).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


class I18n:
    """Language manager helper for UI components."""

    def __init__(self, lang: str = DEFAULT_LANGUAGE) -> None:
        self._lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

    @property
    def lang(self) -> str:
        return self._lang

    @lang.setter
    def lang(self, value: str) -> None:
        if value in SUPPORTED_LANGUAGES:
            self._lang = value

    def t(self, key: str, **kwargs: Any) -> str:
        return get_text(key, lang=self._lang, **kwargs)

    def __call__(self, key: str, **kwargs: Any) -> str:
        return self.t(key, **kwargs)
