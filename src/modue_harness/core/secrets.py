"""Secret masking for everything the harness persists or reports.

에이전트 출력은 칠판 로그·산출물·작업 기록과 CLI/웹 UI 알림에 그대로 남는다. 에이전트가
.env 를 읽거나 키를 출력하면 평문으로 저장되므로, 저장·보고 직전에 두 단계로 가린다.

1. 실제로 설정된 키 값: 환경 변수와 .env 에서 이름이 *_API_KEY, *_TOKEN, *_SECRET,
   *_PASSWORD 등으로 끝나는 변수의 값을 찾아 `[MASKED:<변수명>]` 으로 바꾼다 (오탐 없음).
2. 알려진 키 형식: Anthropic/OpenAI/OpenRouter/Google/GitHub/AWS/Slack 키와 개인 키 블록을
   정규식으로 찾아 `[MASKED:<종류>]` 로 바꾼다 (설정되지 않은 키도 잡는다).

프로젝트 폴더에 에이전트가 작성하는 코드 파일은 대상이 아니다. MODUE_MASK_SECRETS=0 으로 끈다.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple

# 값이 비밀로 취급될 환경 변수 이름 (접미사 기준)
_SECRET_NAME_RE = re.compile(
    r"(?:API_?KEY|ACCESS_?KEY|SECRET_?KEY|PRIVATE_?KEY|_KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?)$",
    re.IGNORECASE,
)
_MIN_SECRET_LEN = 8

# 키가 단어 중간에서 시작하지 않게 한다 (예: "task-decomposition-..." 의 "sk-" 오탐 방지).
_B = r"(?<![A-Za-z0-9_\-])"

# 알려진 키 형식. 순서가 중요하다: 더 구체적인 접두어를 먼저 둔다.
_PATTERNS: List[Tuple[str, Pattern[str]]] = [
    ("PRIVATE_KEY", re.compile(
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.DOTALL
    )),
    ("ANTHROPIC_KEY", re.compile(_B + r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OPENROUTER_KEY", re.compile(_B + r"sk-or-v1-[A-Za-z0-9]{20,}")),
    ("OPENAI_KEY", re.compile(_B + r"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}")),
    ("GOOGLE_API_KEY", re.compile(_B + r"AIza[0-9A-Za-z_\-]{35}")),
    ("GITHUB_TOKEN", re.compile(_B + r"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})")),
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("SLACK_TOKEN", re.compile(_B + r"xox[abposr]-[A-Za-z0-9\-]{10,}")),
    ("BEARER_TOKEN", re.compile(r"(?<=Bearer )[A-Za-z0-9_\-\.=]{20,}")),
]


def masking_enabled() -> bool:
    return os.environ.get("MODUE_MASK_SECRETS", "1").strip().lower() not in ("0", "false", "no", "off")


def _looks_secret(name: str, value: str) -> bool:
    if not _SECRET_NAME_RE.search(name):
        return False
    value = value.strip()
    if len(value) < _MIN_SECRET_LEN or value.isdigit():
        return False
    # *_TOKEN_FILE 같은 경로 값은 가리면 로그 전체의 경로가 사라지므로 제외한다.
    try:
        if os.path.exists(value):
            return False
    except (OSError, ValueError):
        pass
    return True


def _parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            values[key] = val.strip().strip("'\"")
    except OSError:
        pass
    return values


class SecretMasker:
    """Replaces known secret values and well-known key formats with `[MASKED:<label>]`."""

    def __init__(self, env_files: Optional[List[Path]] = None) -> None:
        self._env_files = env_files
        self._file_cache: Dict[Path, Tuple[float, Dict[str, str]]] = {}

    def _env_file_paths(self) -> List[Path]:
        if self._env_files is not None:
            return list(self._env_files)
        return [Path.cwd() / ".env", Path.home() / ".env"]

    def known_secrets(self) -> List[Tuple[str, str]]:
        """(name, value) pairs of secret-looking variables, longest value first."""
        found: Dict[str, str] = {}
        for path in self._env_file_paths():
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            cached = self._file_cache.get(path)
            if not cached or cached[0] != mtime:
                cached = (mtime, _parse_env_file(path))
                self._file_cache[path] = cached
            for name, value in cached[1].items():
                if _looks_secret(name, value):
                    found.setdefault(value, name)
        for name, value in os.environ.items():
            if _looks_secret(name, value):
                found.setdefault(value, name)
        # 긴 값부터 바꿔야 한 값이 다른 값의 일부일 때 조각이 남지 않는다.
        return sorted(((n, v) for v, n in found.items()), key=lambda p: len(p[1]), reverse=True)

    def mask(self, text: Any) -> Any:
        """Mask secrets in a string. Non-strings are returned unchanged."""
        if not isinstance(text, str) or not text or not masking_enabled():
            return text
        return self._mask_str(text, self.known_secrets())

    def mask_obj(self, obj: Any) -> Any:
        """Recursively mask strings inside dicts/lists/tuples (keys are left as-is)."""
        if not masking_enabled():
            return obj
        # 큰 작업 기록(로그 수백 줄)에서 줄마다 환경 변수를 다시 훑지 않도록 한 번만 계산한다.
        return self._mask_any(obj, self.known_secrets())

    def _mask_any(self, obj: Any, known: List[Tuple[str, str]]) -> Any:
        if isinstance(obj, str):
            return self._mask_str(obj, known) if obj else obj
        if isinstance(obj, dict):
            return {k: self._mask_any(v, known) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._mask_any(v, known) for v in obj]
        if isinstance(obj, tuple):
            return tuple(self._mask_any(v, known) for v in obj)
        return obj

    @staticmethod
    def _mask_str(text: str, known: List[Tuple[str, str]]) -> str:
        for name, value in known:
            if value in text:
                text = text.replace(value, f"[MASKED:{name}]")
        for label, pattern in _PATTERNS:
            text = pattern.sub(f"[MASKED:{label}]", text)
        return text


_default_masker = SecretMasker()


def mask_secrets(text: Any) -> Any:
    """Mask secrets in a string using the process-wide masker."""
    return _default_masker.mask(text)


def mask_secrets_obj(obj: Any) -> Any:
    """Mask secrets in nested dict/list data using the process-wide masker."""
    return _default_masker.mask_obj(obj)
