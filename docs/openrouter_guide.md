# OpenRouter 에이전트 어댑터 가이드

`openrouter` 어댑터는 외부 AI CLI 없이 **하네스가 직접 [OpenRouter](https://openrouter.ai) API를 호출**하는 내장 에이전트입니다. 모델이 도구 호출(tool calling)로 파일을 읽고, 쓰고, 테스트를 실행하면 하네스가 그 도구를 **배정된 프로젝트 폴더 안에서만** 실행합니다. 역할마다 서로 다른 모델을 붙여 기획, 개발, 리뷰, 토론을 모두 맡길 수 있습니다.

OpenAI SDK의 OpenAI 호환 API를 사용하므로, `base_url`을 바꾸면 OpenAI 본사나 로컬 Ollama·vLLM·LM Studio 같은 다른 호환 서버에도 같은 어댑터를 쓸 수 있습니다.

---

## 1. 설치와 인증

```bash
pip install -e ".[openrouter]"      # OpenAI SDK(openai>=1.0) 설치
cp .env.example .env                # 이미 있다면 생략
```

`.env`에 [OpenRouter에서 발급한 키](https://openrouter.ai/keys)를 넣습니다. `.env`는 `.gitignore`에 등록되어 있어 커밋되지 않습니다.

```
OPENROUTER_API_KEY=sk-or-...
```

키는 환경변수를 먼저 읽고, 없으면 현재 폴더와 홈 폴더의 `.env`에서 읽습니다.

## 2. agents.yaml 설정

```yaml
agents:
  architect:
    adapter: "openrouter"
    model: "anthropic/claude-sonnet-4.5"
    effort: "high"
    tools: "read"
    role: "System Architect"
  developer:
    adapter: "openrouter"
    model: "qwen/qwen3-coder"
    tools: "full"
    role: "Software Engineer"
  reviewer:
    adapter: "openrouter"
    model: "openai/gpt-5"
    tools: "read"
    role: "Code Reviewer"
```

| 키 | 기본값 | 설명 |
|---|---|---|
| `model` | (필수) | OpenRouter 모델 ID. 도구 호출을 지원해야 합니다 ([지원 모델 목록](https://openrouter.ai/models?supported_parameters=tools)) |
| `tools` | `read` | 도구 권한: `none`, `read`, `full` (아래 표) |
| `effort` | 없음 | OpenRouter `reasoning.effort`로 전달합니다. 추론을 지원하는 모델에만 적용됩니다 |
| `max_turns` | `40` | 도구 호출을 반복하는 최대 횟수. 넘기면 실패로 끝납니다 |
| `allowed_commands` | 기본 허용 목록 | `run_command`로 실행할 수 있는 명령 접두어 목록 |
| `command_timeout` | `120` | `run_command` 한 번의 제한 시간(초) |
| `base_url` | `https://openrouter.ai/api/v1` | 다른 OpenAI 호환 서버 주소 |
| `api_key_env` | `OPENROUTER_API_KEY` | API 키를 읽을 환경변수 이름 |
| `system_instruction` | 없음 | 역할 지시문(시스템 메시지) |

### 도구 권한 (`tools`)

| 값 | 제공 도구 | 권장 역할 |
|---|---|---|
| `none` | 없음 (텍스트 응답만) | 토론, 요약 |
| `read` | `list_dir`, `read_file`, `search` | 기획, 리뷰 |
| `full` | `read` 도구 + `write_file`, `edit_file`, `run_command` | 개발 |

## 3. 안전장치

- **폴더 격리:** 모든 경로를 실제 경로로 풀어서 프로젝트 폴더 안인지 검사합니다. `..`, 절대 경로, 폴더 밖을 가리키는 심볼릭 링크는 거부됩니다.
- **`.git` 보호:** `.git` 안에는 쓸 수 없습니다.
- **`run_command`는 허용 목록 방식입니다.** 명령이 허용 목록의 접두어로 시작할 때만 실행합니다. 기본 허용 목록은 다음과 같습니다.

  ```
  pytest, python -m pytest, python3 -m pytest, python -m unittest, python3 -m unittest,
  python -m py_compile, python3 -m py_compile, git status, git diff, git log, git show, ls, pwd
  ```

  - 셸을 거치지 않으므로 `|`, `>`, `&&`, `;`는 동작하지 않습니다.
  - 인자 중 프로젝트 폴더 밖을 가리키는 경로(`/etc`, `../x`, `--output=/tmp/x`)는 거부됩니다.
  - `allowed_commands`를 지정하면 기본 목록을 **대체**합니다. 빈 목록 `[]`이면 `run_command` 자체를 모델에 제공하지 않습니다.
  - ⚠️ `python`, `npm run`, `make`처럼 임의 코드를 실행하는 명령을 허용하면, 그 코드는 폴더 제한을 받지 않습니다. 신뢰할 수 있는 작업에만 추가하세요.
- **결과 길이 제한:** 도구 결과는 2만 자에서 자르고, 대화가 길어지면 오래된 도구 결과부터 비워 토큰 사용량을 줄입니다.

## 4. 사용량 기록

API 응답의 실제 토큰 수와 OpenRouter가 알려 주는 비용(`cost_usd`)을 기록합니다. 출력 길이로 추정하는 CLI 어댑터와 달리 `is_estimated: false`입니다. `429` 응답은 기존 사용량 한도 감지 로직에 그대로 잡힙니다.

## 5. 다른 OpenAI 호환 서버 사용

```yaml
  local:
    adapter: "openrouter"
    model: "qwen2.5-coder:14b"
    base_url: "http://localhost:11434/v1"   # Ollama
    api_key_env: "OLLAMA_API_KEY"           # 아무 값이나 들어 있으면 됩니다
    tools: "read"
```

`base_url`이 OpenRouter가 아니면 OpenRouter 전용 옵션(`reasoning`, 비용 포함 요청)은 보내지 않습니다.

## 6. 트러블슈팅

| 증상 | 원인과 해결 |
|---|---|
| `requires the OpenAI SDK` | `pip install -e ".[openrouter]"` 로 설치하세요 |
| `API key not found: set OPENROUTER_API_KEY` | `.env` 또는 환경변수에 키를 넣으세요 |
| `OpenRouter API error 402` | OpenRouter 크레딧이 부족합니다 |
| `OpenRouter API error 404` 또는 `400` (tools 관련) | 모델 ID가 틀렸거나 도구 호출을 지원하지 않는 모델입니다 |
| `max_turns (40)` 에서 중단 | 작업을 더 작게 나누거나 `max_turns`를 늘리세요 |
| `command not in allow list` | 필요한 명령을 `allowed_commands`에 추가하세요 |
