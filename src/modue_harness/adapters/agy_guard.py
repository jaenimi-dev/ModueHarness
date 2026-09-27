"""Antigravity (agy) write guard: deny rules that keep agents out of the harness repository.

하네스는 agy 를 --dangerously-skip-permissions 로 실행한다. 이 상태에서는
allowNonWorkspaceAccess 기본값(off)이 무시되어, 파일 도구가 작업 폴더 밖에 그대로 쓴다.
--sandbox 는 터미널 명령만 막고 파일 도구는 막지 못한다.

agy 의 deny 규칙은 --dangerously-skip-permissions 보다 우선하므로, 이 모듈은
~/.gemini/antigravity-cli/settings.json 의 permissions.deny 에 보호 경로를 넣는다.
규칙 우선순위가 Deny > Ask > Allow 라서 "작업 폴더 밖 전부"를 막을 수는 없고,
하네스 저장소의 최상위 항목(projects/, blackboard/ 제외)과 민감한 홈 경로를 나열한다.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional

AGY_SETTINGS_PATH = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"

# 저장소 안에서 에이전트가 써야 하는 폴더 (작업 공간과 칠판, worktree)
DEFAULT_ALLOWED_TOP_LEVEL = ("projects", "blackboard", ".modue_worktrees")

# 홈 디렉터리 기준 민감 경로. 가드 설정 파일 자신도 넣어 에이전트가 규칙을 지우지 못하게 한다.
SENSITIVE_HOME_PATHS = (
    ".ssh",
    ".gnupg",
    ".aws",
    ".config/gcloud",
    ".bashrc",
    ".bash_profile",
    ".profile",
    ".zshrc",
    ".gitconfig",
    ".gemini/antigravity-cli/settings.json",
)


def _rule(path: Path) -> str:
    return f"write_file({path.as_posix()})"


def build_guard_rules(
    harness_root: Path,
    allowed_dirs: Optional[Iterable[Path]] = None,
    home: Optional[Path] = None,
) -> List[str]:
    """Deny rules for every top-level entry of the harness repo except allowed dirs, plus sensitive home paths."""
    root = Path(harness_root).resolve()
    allowed = {Path(p).resolve() for p in (allowed_dirs or [])}
    allowed.update(root / name for name in DEFAULT_ALLOWED_TOP_LEVEL)

    rules: List[str] = []
    if root.is_dir():
        for entry in sorted(root.iterdir(), key=lambda p: p.name):
            resolved = entry.resolve()
            # 허용 폴더 자신이거나, 허용 폴더를 안에 품은 항목은 막으면 작업 공간까지 막힌다.
            if resolved in allowed or any(_is_within(a, resolved) for a in allowed):
                continue
            rules.append(_rule(entry.absolute()))

    home_dir = Path(home) if home else Path.home()
    rules.extend(_rule(home_dir / rel) for rel in SENSITIVE_HOME_PATHS)
    return list(dict.fromkeys(rules))


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _load_settings(settings_path: Path) -> Dict:
    if not settings_path.exists():
        return {}
    text = settings_path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{settings_path} is not a JSON object")
    return data


def _current_deny(data: Dict) -> List[str]:
    deny = (data.get("permissions") or {}).get("deny") or []
    return [r for r in deny if isinstance(r, str)]


def missing_guard_rules(rules: List[str], settings_path: Path = AGY_SETTINGS_PATH) -> List[str]:
    """Rules from `rules` that are not yet present in the agy settings deny list."""
    try:
        present = set(_current_deny(_load_settings(settings_path)))
    except (OSError, ValueError):
        return list(rules)
    return [r for r in rules if r not in present]


def install_guard_rules(rules: List[str], settings_path: Path = AGY_SETTINGS_PATH) -> List[str]:
    """Merge rules into permissions.deny (backing up the file first). Returns the rules that were added."""
    data = _load_settings(settings_path)
    deny = _current_deny(data)
    added = [r for r in rules if r not in deny]
    if not added:
        return []

    if settings_path.exists():
        shutil.copy2(settings_path, settings_path.with_name(settings_path.name + ".modue-backup"))
    permissions = data.get("permissions")
    if not isinstance(permissions, dict):
        permissions = {}
    permissions["deny"] = deny + added
    data["permissions"] = permissions
    _write_atomic(settings_path, data)
    return added


def uninstall_guard_rules(rules: List[str], settings_path: Path = AGY_SETTINGS_PATH) -> List[str]:
    """Remove the given rules from permissions.deny. Returns the rules that were removed."""
    data = _load_settings(settings_path)
    deny = _current_deny(data)
    removed = [r for r in deny if r in set(rules)]
    if not removed:
        return []
    data["permissions"]["deny"] = [r for r in deny if r not in set(rules)]
    _write_atomic(settings_path, data)
    return removed


def _write_atomic(settings_path: Path, data: Dict) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = settings_path.with_name(settings_path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, settings_path)
