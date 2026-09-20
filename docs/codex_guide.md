# ChatGPT Codex CLI 설정 및 연동 가이드

OpenAI의 **Codex CLI**는 터미널 환경에서 코드를 분석, 수정, 실행하고 자동화 작업을 수행할 수 있는 공식 코딩 에이전트 CLI 도구입니다.

---

## 1. 설치 및 업데이트

운영체제 및 환경에 맞는 방식을 선택해 설치합니다.

### 🐧 Linux / 🍎 macOS
```bash
# 설치
curl -fsSL https://chatgpt.com/codex/install.sh | sh

# 업데이트 (동일한 명령어로 최신 버전 갱신)
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

### 🪟 Windows (PowerShell)
```powershell
# 설치 및 업데이트
powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
```

> ⚠️ **중요 (Windows 환경변수 반영)**:  
> 설치가 완료된 후 등록된 환경변수(PATH)를 정상 인식하기 위해 **열려 있는 PowerShell 창을 닫고 새로운 PowerShell 창을 열거나 재기동**해야 `codex` 명령어가 정상 실행됩니다. (기존 터미널 창이나 VS Code 내장 터미널 포함)

### 📦 npm (Node.js 환경)
```bash
# 글로벌 설치
npm install -g @openai/codex

# 업데이트
npm install -g @openai/codex@latest
```

### 🍺 Homebrew (macOS)
```bash
# 설치
brew install --cask codex

# 업데이트
brew upgrade --cask codex
```

---

## 2. 로그인 및 인증 (`codex login`)

Codex CLI 설치가 완료되면, 작업을 시작하기 전에 터미널에서 **`codex login`** 명령을 실행하여 ChatGPT 계정으로 로그인해야 합니다.

```bash
codex login
```

### 🔑 로그인 진행 절차
1. 터미널에 `codex login`을 입력하면 기본 웹 브라우저가 자동으로 열립니다.
2. 브라우저 화면에서 **Sign in with ChatGPT**를 선택하고 보유하신 ChatGPT 계정(Plus, Pro, Team, Enterprise 등)으로 로그인합니다.
3. 브라우저에서 인증 완료 메시지가 나타나면 터미널로 돌아옵니다.
4. 터미널에 `✓ Successfully logged in`과 같은 인증 완료 메시지가 출력되면 정상적으로 설정된 것입니다.

> **참고**:
> - 로그아웃이 필요할 때는 `codex logout` 명령을 사용할 수 있습니다.
> - 현재 로그인 상태 및 계정 확인은 `codex auth status` (또는 `codex whoami`)로 확인 가능합니다.

---

## 3. 실행 모드 및 기본 사용법

인증이 완료된 후에는 프로젝트 폴더에서 **대화형 TUI 모드** 또는 자동화/스크립트용 **비대화형 모드(`codex exec`)**로 실행합니다.

### ① 대화형 모드 (Interactive TUI)
터미널에서 실시간으로 대화하며 코드 수정 및 도구 실행을 조율할 때 사용합니다.
```bash
cd /path/to/your/project
codex
```
- 프롬프트에 `Tell me about this project` 또는 원하는 작업을 자연어로 입력
- 작업 중 이미지 드래그&드롭 또는 붙여넣기 지원
- 파일 수정 및 커맨드 실행 전 승인/거절 인터랙션 제공

### ② 비대화형 모드 (Non-interactive Mode: `codex exec`)
스크립트, CI/CD 파이프라인, ModueHarness 연동 등 백그라운드 자동화 시 사용합니다.
```bash
# 단일 지시문 실행 (최종 결과만 stdout 출력, 진행상황은 stderr)
codex exec "이 프로젝트의 구조를 분석하고 취약점 3가지를 도출해줘"

# 파이프(stdin) 입력과 함께 실행
git diff | codex exec "변경된 코드에 대해 리뷰를 작성해줘" > review.md

# 파일 저장 없이 일회성 세션으로 실행
codex exec --ephemeral "레포지토리 요약"
```

---

## 4. 권한 및 샌드박스 설정 (Permissions & Sandbox)

`codex exec`는 기본적으로 **읽기 전용(read-only)** 샌드박스에서 실행됩니다. 프로젝트 파일 생성/수정이나 명령어 실행이 필요할 경우 권한 플래그를 지정해야 합니다.

| 옵션 | 권한 수준 | 설명 및 용도 |
| :--- | :--- | :--- |
| *(기본값)* | `read-only` | 파일 읽기 및 분석만 가능 (수정 불가) |
| `--sandbox workspace-write` | **작업 디렉터리 쓰기 허용** | 프로젝트 내 소스 코드 및 파일 생성/수정 가능 (**권장**) |
| `--sandbox danger-full-access` | **전체 접근 허용** | 시스템 전역 수정 및 위험 명령 허용 (격리된 Docker/CI 환경에서만 사용) |

```bash
# 일반적인 코드 구현 작업 실행 예시
codex exec --sandbox workspace-write "FastAPI health check 엔드포인트를 추가해줘"
```

---

## 5. 주요 유용한 기능 및 플래그

* **이전 세션 이어하기**:
  ```bash
  codex resume
  ```
* **이미지 첨부 분석**:
  ```bash
  codex --image ./error_screenshot.png "이 에러의 원인과 해결책을 찾아줘"
  ```
* **실시간 웹 검색 활성화**:
  ```bash
  codex --search "최신 Next.js 15 App Router 변경사항을 반영해줘"
  ```
* **JSON 이벤트 스트림 출력 (파싱 및 연동용)**:
  ```bash
  codex exec --json "프로젝트 상태 분석" | jq
  ```
* **MCP (Model Context Protocol) 도구 연동**:
  ```bash
  codex mcp list
  codex mcp add <server-name> <command>
  ```

---

## 6. 전역 환경 설정 (`config.toml`)

전역 기본값은 `~/.codex/config.toml` (또는 `$CODEX_HOME/config.toml`) 파일에서 설정할 수 있습니다.

```toml
# 기본 모델 및 추론 강도 설정 (지원 모델: gpt-5.6-terra, gpt-5.6-luna, gpt-5.5 등)
model = "gpt-5.6-terra"
model_reasoning_effort = "high"

# 기본 권한 설정 (작업 디렉터리 쓰기 허용)
sandbox_mode = "workspace-write"

# 웹 검색 기본 활성화 여부
web_search = true
```

---

## 7. ModueHarness 연동 가이드

`codex login`을 마친 뒤 ModueHarness 멀티 에이전트 팀에 Codex를 작업 에이전트(Worker) 또는 지휘관(Conductor)으로 등록하는 방법입니다.

### 방법 1: 웹 대시보드 UI에서 등록
1. ModueHarness 웹 UI 좌측 `⚙️ AI 팀 및 환경 설정` ➔ `+ AI 추가`
2. **이름**: `codex`
3. **어댑터**: `codex` (공식 Codex 전용 어댑터)
4. **모델**: `gpt-5.6-terra` (또는 `gpt-5.6-luna`, `gpt-5.5`)
5. **추론 강도 (Effort)**: `high` (또는 `medium`, `low`)

### 방법 2: `config/agents.yaml` 파일로 등록
```yaml
agents:
  architect:
    adapter: codex
    model: gpt-5.6-terra
    effort: high
    system_instruction: "You are the software architect. Plan and coordinate tasks."

  developer:
    adapter: codex
    model: gpt-5.6-terra
    effort: medium
    system_instruction: "You are the developer. Implement clean, robust code."

  reviewer:
    adapter: codex
    model: gpt-5.6-luna
    system_instruction: "You verify and review implementation code and write test validations."
```
