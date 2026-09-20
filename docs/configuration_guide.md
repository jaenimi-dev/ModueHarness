# ModueHarness 설정 및 실전 사용 매뉴얼 (Configuration & Setup Guide)

ModueHarness 기본 설치([docs/installation.md](installation.md))를 마친 후, 다양한 AI CLI(Claude Code, Google Antigravity, OpenAI Codex, Aider 등)를 연결하여 팀을 구성하고 실제 프로젝트 작업을 자율적으로 실행하기 위한 **단계별 설정 매뉴얼**입니다.

---

## 🧭 전체 설정 흐름 (Roadmap)

ModueHarness는 **자연어 대화형 CLI 실행(방법 A)**과 **정적 워크플로우 명세 실행(방법 B)**의 두 가지 방식을 모두 지원합니다.

```text
[1단계: AI CLI 도구 준비 및 인증 (Claude, AGY 등)]
       ↓
[2단계: 환경 변수(.env) 설정 (선택 사항: API 키 직접 사용 시)]
       ↓
       ├─────────────────────────────────────────────┐
       ▼ [방법 A: 대화형 CLI 직접 실행 (권장, 퀵스타트)]   ▼ [방법 B: 정적 워크플로우 실행]
[3단계-A: 워크플로우 파일 없이 즉시 실행]             [3단계-B: AI 팀 명세(config/agents.yaml) 작성]
 - 터미널에서 대화형 모드(REPL) 진입 (-i)              [4단계-B: 작업 명세(config/workflow.yaml) 작성]
 - 또는 단일 자연어 명령으로 프로젝트에 직접 지시       [5단계-B: modue-harness run 명령 실행]
       │                                             │
       └──────────────────────┬──────────────────────┘
                              ▼
[최종 단계: 공용 칠판(blackboard/) 정보 교환 및 프로젝트 폴더(projects/) 구현 결과 확인]
```

> 💡 **핵심 아키텍처 원칙 (정보 교환 vs 실제 구현)**:  
> - **공용 칠판 (`blackboard/`)**: AI 에이전트 간 상태(`state.json`), 태스크(`tasks/`), 계획 및 종합 보고서(`artifacts/`), 프로세스 로그(`logs/`)를 교환하는 팀 협업 전용 공간입니다.
> - **프로젝트 작업 공간 (`projects/<프로젝트명>/`)**: AI 팀이 실제 소스 코드, 패키지 파일, 단위 테스트를 직접 작성하고 수정하는 프로젝트별 격리 작업 폴더입니다.
> - **건너뛰기(Skip) 가능 여부**: `claude` 브라우저 로그인을 마쳤다면 `.env`를 생성할 필요가 없으며, 워크플로우 파일 없이 곧바로 CLI에서 명령을 내려 작업을 시작할 수 있습니다.

---

## 1단계: 대상 AI CLI 도구 준비 및 인증 확인

ModueHarness는 사용자의 시스템에 설치된 실제 AI CLI 명령어를 서브프로세스로 구동합니다. 사용하고자 하는 도구가 설치되어 있고 인증되었는지 확인합니다.

### 1. Anthropic Claude Code (`claude`)
- **공식 권장 설치 (자동 업데이트 지원)**:
  - macOS, Linux, WSL:
    ```bash
    curl -fsSL https://claude.ai/install.sh | bash
    ```
  - Windows PowerShell:
    ```powershell
    irm https://claude.ai/install.ps1 | iex
    ```
    > 💡 **Windows PATH 등록 알림 발생 시 (범용 해결책)**:  
    > `$userPath = [Environment]::GetEnvironmentVariable("Path", "User"); [Environment]::SetEnvironmentVariable("Path", "$userPath;$HOME\.local\bin", "User"); $env:Path += ";$HOME\.local\bin"`  
    > (또는 GUI 환경 변수 `Path`에 `%USERPROFILE%\.local\bin` 추가)
  - 대안: `npm install -g @anthropic-ai/claude-code` 또는 `brew install --cask claude-code`
- **인증 (아래 2가지 중 택일)**:
  - **방법 A (브라우저 로그인, 권장)**: 터미널에서 `claude`를 실행하여 브라우저 OAuth 인증 완료 (Pro, Max, Team 계정). 로그인 완료 후 터미널에 나타나는 안내에서 **`No, exit`를 선택하거나 `/exit`로 종료**해도 인증 토큰이 로컬에 안전하게 저장됩니다.
  - **방법 B (API 키)**: `.env` 파일 또는 쉘 환경에 `ANTHROPIC_API_KEY` 설정 (Console API)
- **비인터랙티브(헤드리스) 동작 검증**:
  ModueHarness가 자동으로 쿼리를 실행하도록 하려면 `-p` 플래그가 지원되어야 합니다:
  ```bash
  claude -p "Respond only with PONG"
  ```
- 💡 **상세 매뉴얼**: 공식 빠른 시작 가이드 및 프롬프팅 모범 사례, `CLAUDE.md` 연계는 **[docs/claude_guide.md](claude_guide.md)**를 참조하십시오.

### 2. Google Antigravity (`agy`)
- **공식 원라인 설치**:
  - macOS / Linux: `curl -fsSL https://antigravity.google/cli/install.sh | bash`
  - Windows PowerShell: `irm https://antigravity.google/cli/install.ps1 | iex`
  - Windows CMD: `curl -fsSL https://antigravity.google/cli/install.cmd -o install.cmd && install.cmd && del install.cmd`
- **인증**:
  터미널에서 `agy` 실행 후 브라우저 Google 계정 로그인 또는 `GEMINI_API_KEY` 환경 변수 설정
- **비인터랙티브 동작 검증**:
  ```bash
  agy -p "Say OK" --dangerously-skip-permissions
  ```
- 💡 **상세 매뉴얼**: OS별 설치 및 상세 설정, 하이브리드 팀 구성은 **[docs/antigravity_guide.md](antigravity_guide.md)**를 참조하십시오.

### 3. Aider (`aider`)
- **설치**:
  ```bash
  pip install aider-chat
  ```
- **인증**:
  `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY`를 환경 변수로 설정
- **동작 검증**:
  ```bash
  aider --message "echo OK" --yes-always --no-git
  ```

### 4. OpenAI ChatGPT Codex (`codex`)
- **설치**:
  - macOS / Linux: `curl -fsSL https://chatgpt.com/codex/install.sh | sh`
  - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"`  
    *(설치 후 새로운 PowerShell 창을 열거나 재기동하여 PATH 적용)*
- **인증**:
  ```bash
  codex login
  ```
- **지원 모델**: `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`
- **동작 검증**:
  ```bash
  codex exec --sandbox workspace-write "echo OK"
  ```
- 💡 **상세 매뉴얼**: 설치 및 권한, 모델 설정, ModueHarness 연동 방법은 **[docs/codex_guide.md](codex_guide.md)**를 참조하십시오.

### 5. 로컬 LLM 및 범용 스크립트 (`generic`)
- Ollama(`ollama run llama3`), 로컬 Python 스크립트, Shell 명령 등은 별도 클라우드 API 키 없이 즉시 `generic` 어댑터로 등록할 수 있습니다.

---

## 2단계: 환경 변수(`.env`) 설정 (선택 사항)

> ⚡ **잠깐! 이 단계를 건너뛰어도 되나요?**  
> - **건너뛰기 가능 (Skip)**: 1단계에서 터미널을 통해 `claude` 브라우저 로그인을 완료하셨다면 인증 토큰이 로컬에 보관되므로 **`.env` 파일이 필요 없습니다. 바로 실행 단계로 넘어가세요.**  
> - **설정 필요**: Claude Console 선불 API 키(`ANTHROPIC_API_KEY`)를 직접 쓰거나, Aider를 사용하기 위해 `OPENAI_API_KEY`를 등록해야 할 때만 아래 과정을 진행합니다.

ModueHarness는 CLI 실행 시 프로젝트 루트의 `.env` 파일을 자동으로 감지하여 하위 AI CLI 서브프로세스에 환경 변수로 전달합니다.

### 1. 템플릿 복사
```bash
cp .env.example .env
```

### 2. API 키 입력 (`.env`)
```bash
# Anthropic Claude (브라우저 로그인 대신 API 키를 사용할 경우에만 입력)
ANTHROPIC_API_KEY=sk-ant-api03-...

# OpenAI (Aider 등에서 사용)
OPENAI_API_KEY=sk-proj-...

# Google Gemini / Antigravity
GEMINI_API_KEY=AIzaSy...
```
> **참고**: `.env` 파일은 프로젝트의 `.gitignore`에 등록되어 있으므로 Git 저장소로 유출되지 않습니다.

---

## 3단계 (방법 A - 추천): 워크플로우 파일 없이 CLI로 직접 실행하기

ModueHarness는 복잡한 YAML 설정 파일을 작성하지 않고도, **CLI에서 직접 자연어로 명령을 내려 프로젝트 개발 작업을 수행**할 수 있습니다. 시스템에 설치된 `claude` 또는 `agy`를 자동으로 감지하여 팀을 구성합니다.

> 💡 **실행 방식 선택 (아래 3가지 중 가장 편한 방법을 사용하세요)**:  
> 1. **루트 실행 파일 (`python run.py [옵션]`, 가장 추천)**:  
>    Windows, macOS, Linux 어디서든 환경 변수 설정이나 사전 설치 없이 즉시 실행할 수 있습니다.
> 2. **전용 CLI 명령어 (`modue-harness [옵션]`)**:  
>    `pip install -e .` 설치 후 터미널 어디서든 전용 명령어로 바로 실행할 수 있습니다.
> 3. **파이썬 모듈 실행 (`python -m modue_harness.cli [옵션]`)**:  
>    - Linux/macOS: `PYTHONPATH=src python3 -m modue_harness.cli ...`
>    - Windows PowerShell: `$env:PYTHONPATH="src"; python -m modue_harness.cli ...`

> ⚠️ **`ModuleNotFoundError: No module named 'modue_harness'` 오류 해결**:  
> Windows에서 `python -m modue_harness.cli` 실행 시 이 에러가 발생한다면 파이썬이 `src/` 경로를 찾지 못하는 상태입니다.  
> - **해결 1**: `python run.py -i -P <프로젝트명>` 명령어로 실행 (자동으로 `src/` 경로 인식).  
> - **해결 2**: 프로젝트 폴더에서 `pip install -e .` 명령어를 1회 실행하여 패키지 등록.  
> - **해결 3**: PowerShell에서 `$env:PYTHONPATH="src"` 환경 변수 등록 후 실행.

---

### 1. 대화형 CLI 모드 (Interactive REPL)
터미널에서 대화형 프롬프트를 띄우고 연속적으로 지시를 내립니다:

```bash
# [가장 간편] 루트 실행 파일 사용 (Windows / Mac / Linux 공통)
python run.py -i -P my-web-app

# [전용 CLI] pip install -e . 설치 후 사용
modue-harness -i -P my-web-app

# [모듈 직접 실행]
# Linux / macOS (Bash)
PYTHONPATH=src python3 -m modue_harness.cli -i -P my-web-app
# Windows PowerShell
$env:PYTHONPATH="src"; python -m modue_harness.cli -i -P my-web-app
```

**대화형 화면 예시:**
```text
================================================================
🤖 ModueHarness (모두의 하네스) - 대화형 CLI 모드
================================================================
• 대상 프로젝트 (구현 위치): /path/to/projects/my-web-app
• 공용 칠판 (AI 정보 교환):  /path/to/blackboard
• 참여 AI 팀:               architect, developer, reviewer (Leader: architect)
----------------------------------------------------------------
명령어를 입력하면 AI 팀이 프로젝트 디렉터리에 직접 구현합니다.
특수 명령어: /model, /effort, /timeout, /cmd, /jobs, /cancel, /project <이름>, /projects, /files, /status, /help, exit
================================================================

[my-web-app] > FastAPI 기반 사용자 인증 엔드포인트와 단위 테스트 코드를 작성해줘
```

**대화형 모드 특수 명령어 및 실행 팁:**
- `자연어 명령 &` (또는 `/bg <명령어>`): **백그라운드 비동기 실행** (명령을 백그라운드로 보내고 프롬프트가 즉시 반환되어 다른 작업을 계속 입력할 수 있습니다!)
- `/model [에이전트명] [모델명]`: AI 모델 확인 및 실시간 변경 (예: `/model sonnet`, `/model gemini-3.8-flash-high`)
- `/effort [에이전트명] [레벨]`: 추론 노력(Effort) 깊이 변경 (low, medium, high, max, off)
- `/timeout [초|off]`: AI 실행 타임아웃 설정 또는 해제 (기본값: 해제됨 / 무제한 대기)
- `/cmd` (또는 `/last-cmd`): 최근 실행된 실제 AI CLI 전체 명령어 목록 확인
- `/jobs`: 백그라운드 작업 목록, 현재 진행 단계(Stage), 경과 시간, 실패 시 상세 사유 실시간 조회
- `/cancel [job_id]` (또는 `/stop`): 실행 중인 작업 즉시 취소
- `/project <이름>` (또는 `/p <이름>`): 활성 프로젝트 변경 (폴더 자동 생성)
- `/projects`: 생성된 프로젝트 목록 조회
- `/files` (또는 `/ls`): 현재 프로젝트 내 소스코드 파일 목록 확인
- `/status`: 공용 칠판, 활성 프로젝트 및 백그라운드 작업 현황 요약
- `/help`: 도움말
- `exit` / `quit` / `q`: 세션 종료

**투명한 실행 및 실패 원인 안내:**
- **실제 실행 CLI 표시**: `💻 CLI 실행: ...`을 통해 에이전트에게 전달되는 전체 명령어를 축약 없이 터미널에 투명하게 출력합니다.
- **실패 원인 상세 리포트**: 에이전트 작업이나 서브태스크가 실패할 경우 `❌ [실패 상세 원인]` 및 `❌ 오류 상세: <stderr 에러 메시지>`를 즉시 화면에 명시하여 원인을 손쉽게 파악할 수 있습니다.

---

### 2. 단일 명령 직접 실행 (One-shot Command)
대화형 모드에 진입하지 않고 터미널 한 줄로 작업을 지시합니다:

```bash
# [가장 간편] 루트 실행 파일 사용 (Windows / Mac / Linux 공통)
python run.py "계산기 파이썬 모듈과 pytest 테스트를 구현해줘" -P calculator

# [Antigravity 지정 실행]
python run.py "계산기 모듈 구현" -P calculator --agent agy -m gemini-3.8-flash-high -e high

# [전용 CLI] pip install -e . 설치 후 사용
modue-harness "계산기 파이썬 모듈과 pytest 테스트를 구현해줘" -P calculator

# [플래그 사용 예시]
python run.py -p "REST API 서버 구현" -P my-api
```

---

### 3. 기존 Git / GitHub 저장소 연동 가이드 (`git`, `gh` CLI 활용)

이미 존재하는 외부 Git 또는 GitHub 저장소의 코드를 분석, 리팩토링하거나 새로운 기능을 추가할 때는 **`projects/` 디렉터리 안에 저장소를 클론한 뒤, 그 폴더명을 `-P` 옵션으로 지정**하여 실행합니다.

#### 1) 저장소 클론 (Clone)
`projects/` 폴더 아래로 대상 저장소를 클론합니다:

```bash
# 방법 A: 표준 Git 명령어 사용
git clone https://github.com/my-org/my-service.git projects/my-service

# 방법 B: GitHub CLI (gh) 사용
gh repo clone my-org/my-service projects/my-service
```

> 💡 **왜 `projects/<저장소명>`으로 클론해야 하나요?**  
> ModueHarness는 AI 에이전트(Claude Code, Google Antigravity 등)를 실행할 때 `projects/<저장소명>`을 서브프로세스의 작업 디렉터리(`cwd`)로 지정합니다.  
> 따라서 저장소가 이 위치에 있으면 AI가 기존 소스코드 파일, 패키지 의존성(`package.json`, `pyproject.toml` 등), Git 버전 관리 내역(`.git`)을 그대로 인식하여 정확하고 안전하게 작업을 진행합니다.

#### 2) ModueHarness 실행 (`-P <저장소명>`)
클론한 디렉터리 이름을 `-P` 인자로 전달합니다:

```bash
# 대화형 모드(REPL)로 시작
python run.py -i -P my-service

# 또는 단일 명령으로 즉시 실행
python run.py "기존 코드베이스 구조를 파악하고, 누락된 단위 테스트 코드를 pytest로 작성해줘" -P my-service
```

#### 3) Git 협업 실전 팁
- **브랜치 생성 및 자동 커밋 지시**:
  ```text
  [my-service] > feature/auth 브랜치를 새로 생성하고, JWT 인증 모듈을 구현한 뒤 변경사항을 커밋해줘.
  ```
  Claude Code와 Antigravity는 터미널 실행 권한을 가지고 있으므로, 브랜치 분기(`git checkout -b`)부터 커밋(`git commit`)까지 자율적으로 처리합니다.
- **안전한 원격 푸시**:
  AI가 작업을 마친 후 터미널에서 사용자가 직접 `git status` 및 `git diff`로 코드 변경 내역을 확인한 뒤 `git push origin <브랜치명>`을 수행하는 것을 권장합니다.

---

### 4. Web UI 및 터미널 TUI 대시보드 활용

터미널 CLI 외에도 직관적인 그래픽/텍스트 기반 콕핏 대시보드를 통해 다중 AI 팀의 작업 현황과 산출물을 모니터링할 수 있습니다:

- **Web UI 대시보드 (NiceGUI)**: 웹 브라우저에서 3분할 화면(명령 입력기, 실시간 AI 로그 스트림, 칠판 산출물 및 생성된 소스 코드 뷰어)을 제공합니다.
  ```bash
  python run.py --ui -P my-web-app
  # (또는 pip 설치 후: modue-harness ui -P my-web-app)
  ```
- **Terminal TUI 대시보드 (Textual)**: SSH 원격 서버 또는 순수 터미널 콘솔에서 동작하는 풀스크린 대시보드입니다.
  ```bash
  python run.py --tui -P my-web-app
  # (또는 pip 설치 후: modue-harness tui -P my-web-app)
  ```

#### ⚠️ UI 의존성 누락 시 해결 방법 (Troubleshooting)
ModueHarness는 기본 코어 CLI를 최대한 가볍게 유지하기 위해 NiceGUI와 Textual을 **선택적 의존성(Optional Dependency)**으로 분리해 두었습니다.

UI 패키지가 설치되지 않은 상태에서 UI 명령어를 실행하면 다음과 같은 친절한 가이드 메시지가 표시됩니다:

```text
$ modue-harness ui
🌐 Starting ModueHarness Web UI at http://127.0.0.1:8080 ...
❌ NiceGUI is not installed. Please install it using: pip install 'modue-harness[ui]' or pip install nicegui
```

```text
$ modue-harness tui
❌ Textual is not installed. Please install it using: pip install 'modue-harness[ui]' or pip install textual
```

**해결 방법**:  
터미널에서 아래 명령어 중 하나를 실행하여 UI 의존성을 설치하면 즉시 정상 동작합니다:
```bash
# ModueHarness UI 패키지 일괄 설치 (NiceGUI + Textual)
pip install "modue-harness[ui]"

# 또는 소스 코드 개발 모드에서 설치 시
pip install -e ".[ui]"
# (전체 패키지 일괄 설치: pip install -e ".[all]")
```

---

## 4단계 (방법 B - 고급): 설정 폴더(`config/`) 기반 AI 팀 및 워크플로우 구성

고정된 다단계 파이프라인(예: CI/CD 연계, 조건부 재시도 릴레이 등)이 필요한 경우, `config/` 디렉터리에 AI 팀 명세와 작업 명세를 선언적으로 작성할 수 있습니다.

### 📂 디렉터리 구조
```text
ModueHarness/
├── config/
│   ├── agents.example.yaml     <-- [제공되는 템플릿] GitHub 관리
│   ├── workflow.example.yaml   <-- [제공되는 템플릿] GitHub 관리
│   ├── agents.yaml             <-- [복사해서 사용] .gitignore로 로컬 보호
│   └── workflow.yaml           <-- [복사해서 사용] .gitignore로 로컬 보호
├── blackboard/                 <-- [정보 교환] 상태, 태스크 큐, 계획, 로그
├── projects/                   <-- [실제 구현] 프로젝트별 소스코드 (.gitignore 보호)
│   ├── my-web-app/
│   └── calculator/
└── src/
```

### 1. 템플릿 복사
```bash
cp config/agents.example.yaml config/agents.yaml
cp config/workflow.example.yaml config/workflow.yaml
```

### 2. AI 팀 명세(`config/agents.yaml`)
Claude Code, Google Antigravity, Aider 등 팀원별로 어댑터와 모델, 추론 노력을 자유롭게 지정할 수 있습니다:

```yaml
version: "0.6.0"
name: "my-engineering-team"

agents:
  # 1. 아키텍트 (Claude Code - 심층 추론)
  architect:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]
    model: "claude-3-7-sonnet-latest"
    effort: "high"
    role: "System Architect & Technical Planner"
    system_instruction: "You design clean, modular software architecture specifications."

  # 2. 소프트웨어 개발자 (Google Antigravity - 초고속 구현)
  developer:
    adapter: "antigravity"
    command: "agy"
    args: ["--dangerously-skip-permissions"]
    model: "gemini-3.8-flash-high"
    effort: "medium"
    role: "Core Implementation Engineer"
    system_instruction: "You write robust, production-ready code matching the specifications."

  # 3. 품질 & 보안 리뷰어 (Claude Code)
  reviewer:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]
    model: "claude-3-7-sonnet-latest"
    effort: "high"
    role: "Quality and Security Reviewer"
    system_instruction: "You critically review code for edge cases and security vulnerabilities."
```

### 3. 작업 명세(`config/workflow.yaml`)
```yaml
version: "0.6.0"
name: "feature-delivery-pipeline"
agents_file: "agents.yaml"

workflow:
  topology: "pipeline"
  timeout_per_step: 300
  steps:
    - id: "step_plan"
      agent: "architect"
      instruction: "Write a technical specification for token-bucket rate limiter in spec.md."
      output_artifact: "spec.md"

    - id: "step_code"
      agent: "developer"
      condition: "artifact_exists:spec.md"
      input_artifacts: ["spec.md"]
      instruction: "Read spec.md and implement the rate limiter in ratelimiter.py."
      output_artifact: "ratelimiter.py"
      retry_count: 1

    - id: "step_review"
      agent: "reviewer"
      input_artifacts: ["spec.md", "ratelimiter.py"]
      instruction: "Review ratelimiter.py against spec.md and write a review report in review.md."
      output_artifact: "review.md"
```

### 4. 워크플로우 실행
- **Linux / macOS (Bash)**:
  ```bash
  PYTHONPATH=src python3 -m modue_harness.cli run -c config/workflow.yaml --report report.md
  ```
- **Windows PowerShell**:
  ```powershell
  $env:PYTHONPATH="src"; python -m modue_harness.cli run -c config/workflow.yaml --report report.md
  ```

---

## 5단계: 프로젝트 관리 및 공용 칠판 산출물 점검

### 1. 프로젝트 목록 조회
생성된 프로젝트 목록을 확인합니다:
```bash
python3 -m modue_harness.cli projects
```

### 2. 공용 칠판 및 세션 상태 점검
칠판 상태, 활성 프로젝트, 등록된 태스크와 아티팩트를 확인합니다:
```bash
python3 -m modue_harness.cli status
```

### 3. 산출물 및 구현 코드 확인
- **실제 소스 코드 및 구현 파일**: `projects/<프로젝트명>/` 에서 확인
- **AI 간 계획 및 종합 보고서**: `blackboard/artifacts/plan.md`, `blackboard/artifacts/synthesis_report.md` 에서 확인
- **실행 원시 로그**: `blackboard/logs/` 에서 확인
