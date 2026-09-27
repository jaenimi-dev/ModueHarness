"""Tests for secret masking in persisted blackboard data and reported summaries."""

import json
import sys
from pathlib import Path

import pytest

from modue_harness.core.blackboard import Blackboard
from modue_harness.core.secrets import SecretMasker, mask_secrets
from modue_harness.core.types import Task, TaskStatus

OPENROUTER = "sk-or-v1-" + "a1" * 32
ANTHROPIC = "sk-ant-api03-" + "B" * 40
OPENAI = "sk-proj-" + "c" * 40
GOOGLE = "AIza" + "D" * 35
GITHUB = "ghp_" + "e" * 36
AWS = "AKIA" + "F" * 16
PRIVATE_KEY = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\ndef\n-----END OPENSSH PRIVATE KEY-----"


@pytest.fixture
def masker(tmp_path: Path, monkeypatch) -> SecretMasker:
    for name in list(__import__("os").environ):
        if name.endswith(("KEY", "TOKEN", "SECRET", "PASSWORD")):
            monkeypatch.delenv(name, raising=False)
    return SecretMasker(env_files=[])


# ------------------------------------------------------------------ known values
def test_env_secret_value_is_masked_with_its_name(masker, monkeypatch):
    monkeypatch.setenv("MY_SERVICE_API_KEY", "custom-secret-value-123")
    assert masker.mask("key=custom-secret-value-123;") == "key=[MASKED:MY_SERVICE_API_KEY];"


def test_dotenv_secret_value_is_masked(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text('# comment\nexport DB_PASSWORD="hunter2-very-long"\nDEBUG=true\n', encoding="utf-8")
    m = SecretMasker(env_files=[env])
    assert m.mask("pw hunter2-very-long, debug true") == "pw [MASKED:DB_PASSWORD], debug true"


def test_dotenv_changes_are_picked_up(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("A_TOKEN=first-token-value\n", encoding="utf-8")
    m = SecretMasker(env_files=[env])
    assert "[MASKED:A_TOKEN]" in m.mask("first-token-value")
    import os
    import time

    env.write_text("A_TOKEN=second-token-value\n", encoding="utf-8")
    os.utime(env, (time.time() + 5, time.time() + 5))
    assert "[MASKED:A_TOKEN]" in m.mask("second-token-value")


@pytest.mark.parametrize(
    "name,value",
    [
        ("SHORT_TOKEN", "abc"),           # too short
        ("PIN_PASSWORD", "12345678"),     # digits only
        ("PATH_LIKE_TOKEN", "/usr/bin"),  # existing path
        ("HOME", "not-a-secret-value"),   # name is not secret-like
    ],
)
def test_non_secret_values_are_left_alone(masker, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    assert masker.mask(f"x {value} y") == f"x {value} y"


def test_longer_secret_is_replaced_before_its_prefix(masker, monkeypatch):
    monkeypatch.setenv("SHORT_API_KEY", "abcdefgh1234")
    monkeypatch.setenv("LONG_API_KEY", "abcdefgh1234-extended")
    assert masker.mask("abcdefgh1234-extended") == "[MASKED:LONG_API_KEY]"


# ------------------------------------------------------------------ key formats
@pytest.mark.parametrize(
    "secret,label",
    [
        (OPENROUTER, "OPENROUTER_KEY"),
        (ANTHROPIC, "ANTHROPIC_KEY"),
        (OPENAI, "OPENAI_KEY"),
        (GOOGLE, "GOOGLE_API_KEY"),
        (GITHUB, "GITHUB_TOKEN"),
        (AWS, "AWS_ACCESS_KEY"),
        (PRIVATE_KEY, "PRIVATE_KEY"),
    ],
)
def test_known_key_formats_are_masked(masker, secret, label):
    out = masker.mask(f"found: {secret} (end)")
    assert out == f"found: [MASKED:{label}] (end)"


def test_bearer_token_keeps_the_header_name(masker):
    assert masker.mask("Authorization: Bearer " + "t" * 30) == "Authorization: Bearer [MASKED:BEARER_TOKEN]"


@pytest.mark.parametrize(
    "text",
    [
        "task-decomposition-with-many-extra-words-here",
        "risk-assessment-for-the-new-deployment-plan",
        "def ask_user_for_confirmation_before_running(): pass",
        "normal log line with sk- inside",
    ],
)
def test_no_false_positives_on_ordinary_text(masker, text):
    assert masker.mask(text) == text


def test_masking_can_be_disabled(masker, monkeypatch):
    monkeypatch.setenv("MODUE_MASK_SECRETS", "0")
    assert masker.mask(OPENROUTER) == OPENROUTER
    assert masker.mask_obj({"a": OPENROUTER}) == {"a": OPENROUTER}


def test_mask_obj_masks_nested_values_but_not_keys(masker):
    data = {"logs": [f"line {OPENAI}", {"err": GOOGLE}], "n": 3, OPENAI: "k", "t": (GITHUB,)}
    out = masker.mask_obj(data)
    assert out["logs"] == ["line [MASKED:OPENAI_KEY]", {"err": "[MASKED:GOOGLE_API_KEY]"}]
    assert out["n"] == 3
    assert out[OPENAI] == "k"
    assert out["t"] == ("[MASKED:GITHUB_TOKEN]",)


# -------------------------------------------------------------- blackboard writes
@pytest.fixture
def board(tmp_path: Path) -> Blackboard:
    b = Blackboard(tmp_path / "board")
    b.initialize()
    return b


def _all_text(root: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file())


def test_blackboard_masks_logs_artifacts_jobs_tasks_and_state(board: Blackboard, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", OPENROUTER)

    board.append_log("dev", "s1", f"env dump: OPENROUTER_API_KEY={OPENROUTER}")
    board.write_artifact("report.md", f"key {ANTHROPIC}", metadata={"note": OPENAI}, author_agent="dev")
    board.save_job({"id": "job1", "logs": [f"err {GOOGLE}"], "error": GITHUB})
    task = Task(id="t1", title="t", description=f"use {AWS}", assigned_agent="dev")
    board.create_task(task)
    board.update_task_status("t1", TaskStatus.FAILED, {"error": PRIVATE_KEY})
    board.update_state({"goal": f"deploy with {OPENAI}"})

    text = _all_text(board.root_dir)
    for secret in (OPENROUTER, ANTHROPIC, OPENAI, GOOGLE, GITHUB, AWS, "abc\ndef"):
        assert secret not in text
    assert "[MASKED:OPENROUTER_API_KEY]" in text
    assert "[MASKED:ANTHROPIC_KEY]" in board.read_artifact("report.md")


def test_artifact_history_of_unmasked_legacy_version_is_masked(board: Blackboard):
    path = board.resolve_artifact_path("plan.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"legacy {OPENAI}", encoding="utf-8")  # 마스킹 도입 전에 저장된 파일

    board.write_artifact("plan.md", "new version")

    history = list((board.artifacts_dir / ".history").glob("plan_*.md"))
    assert history and OPENAI not in history[0].read_text(encoding="utf-8")


# ------------------------------------------------------------ engine summaries
def test_pipeline_summary_and_logs_are_masked(tmp_path: Path, monkeypatch):
    from modue_harness.adapters.generic import GenericCLIAdapter
    from modue_harness.engine.pipeline import PipelineRunner
    from modue_harness.engine.workflow import WorkflowAgentConfig, WorkflowConfig, WorkflowStepConfig

    leaky = GenericCLIAdapter(
        name="dev",
        command=sys.executable,
        default_args=["-c", f"import sys; print('out {OPENROUTER}'); sys.exit('boom {ANTHROPIC}')"],
    )
    config = WorkflowConfig(
        name="leak",
        agents={"dev": WorkflowAgentConfig(name="dev")},
        steps=[WorkflowStepConfig(id="s1", agent="dev", instruction="x", output_artifact="out.md")],
    )
    board = Blackboard(tmp_path / "board")
    board.initialize()
    summary = PipelineRunner(config=config, blackboard=board, workspace_dir=tmp_path, adapters_override={"dev": leaky}).run()

    dumped = json.dumps(summary, default=str) + _all_text(board.root_dir)
    assert OPENROUTER not in dumped and ANTHROPIC not in dumped
    assert "[MASKED:ANTHROPIC_KEY]" in summary["steps"][0]["error_message"]


def test_conductor_notifications_are_masked():
    from modue_harness.engine.conductor import ConductorRunner

    received = []
    runner = ConductorRunner.__new__(ConductorRunner)
    runner.progress_callback = lambda event, data: received.append((event, data))

    runner._notify("task_end", {"error": f"failed with {OPENAI}", "nested": [GOOGLE]})

    assert received == [("task_end", {"error": "failed with [MASKED:OPENAI_KEY]", "nested": ["[MASKED:GOOGLE_API_KEY]"]})]


def test_module_level_helper(monkeypatch):
    assert mask_secrets(f"x {GITHUB}") == "x [MASKED:GITHUB_TOKEN]"
    assert mask_secrets(None) is None
