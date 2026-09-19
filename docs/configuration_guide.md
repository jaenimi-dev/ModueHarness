# ModueHarness 설정 및 실전 사용 매뉴얼 (Configuration & Setup Guide)

ModueHarness 설치를 마친 후, 실제로 다양한 AI CLI(Claude Code, Google Antigravity, Aider 등)를 연결하여 팀을 구성하고 작업을 실행하기 위한 **단계별 설정 매뉴얼**입니다.

---

## 🧭 전체 설정 흐름 (Roadmap)

```text
[1단계: AI CLI 도구 준비 및 인증]
       ↓
[2단계: 환경 변수(.env) 설정]
       ↓
[3단계: AI 팀 명세(agents.yaml) 작성]
       ↓
[4단계: 작업 명세(workflow.yaml) 작성]
       ↓
[5단계: 실행 및 블랙보드 산출물 확인]
```

---

## 1단계: 대상 AI CLI 도구 준비 및 인증 확인

ModueHarness는 사용자의 시스템에 설치된 실제 AI CLI 명령어를 서브프로세스로 구동합니다. 사용하고자 하는 도구가 설치되어 있고 인증되었는지 확인합니다.

### 1. Anthropic Claude Code (`claude`)
- **설치**:
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```
- **인증 (아래 2가지 중 택일)**:
  - **방법 A (브라우저 로그인)**: 터미널에서 `claude`를 실행하여 브라우저 OAuth 인증 완료
  - **방법 B (API 키)**: `.env` 파일 또는 쉘 환경에 `ANTHROPIC_API_KEY` 설정
- **비인터랙티브(헤드리스) 동작 검증**:
  ModueHarness가 자동으로 질문에 답변하도록 하려면 `-p` 플래그가 지원되어야 합니다:
  ```bash
  claude -p "Respond only with PONG"
  ```

### 2. Google Antigravity (`agy`)
- **인증**:
  터미널에서 Google 계정 로그인 또는 Gemini API 환경 변수 설정
  ```bash
  agy auth status  # 또는 agy auth login
  ```
- **동작 검증**:
  ```bash
  agy "echo OK"
  ```

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

### 4. 로컬 LLM 및 범용 스크립트 (`generic`)
- Ollama(`ollama run llama3`), 로컬 Python 스크립트, Shell 명령 등은 별도 클라우드 API 키 없이 즉시 `generic` 어댑터로 등록할 수 있습니다.

---

## 2단계: 환경 변수(`.env`) 설정

ModueHarness는 CLI 실행 시 프로젝트 루트의 `.env` 파일을 자동으로 감지하여 하위 AI CLI 프로세스에 전달합니다.

### 1. 템플릿 복사
```bash
cp .env.example .env
```

### 2. API 키 입력 (`.env`)
```bash
# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-api03-...

# OpenAI (Aider 등에서 사용)
OPENAI_API_KEY=sk-proj-...

# Google Gemini / Antigravity
GEMINI_API_KEY=AIzaSy...
```
> **참고**: `.env` 파일은 프로젝트의 `.gitignore`에 등록되어 있으므로 Git 저장소로 유출되지 않습니다.

---

## 3단계: AI 팀 명세(`agents.yaml`) 작성

어떤 AI CLI 도구와 모델, 역할을 가진 팀원들로 구성할지 정의합니다. 한 번 작성해 두면 여러 프로젝트나 작업에서 재사용할 수 있습니다.

### 작성 예시 (`my_team.yaml`)
```yaml
version: "0.4.0"
name: "my-engineering-team"

agents:
  # 1. 아키텍트 / 기획자 (Claude Code)
  architect:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]  # 프롬프트 입력 자동 승인 모드
    role: "System Architect & Technical Planner"
    system_instruction: "You design clean, modular software architecture."

  # 2. 구현 엔지니어 (Antigravity CLI)
  developer:
    adapter: "agy"
    command: "agy"
    role: "Core Implementation Engineer"

  # 3. 코드 리뷰어 (Claude Code 또는 Aider)
  reviewer:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]
    role: "Security and Quality Reviewer"
```

> 💡 **핵심 팁 (프롬프트 멈춤 방지)**:
> AI CLI가 "파일을 수정하시겠습니까? (Y/N)" 같은 대화형 확인 프롬프트를 띄우면 자동화 프로세스가 멈출 수 있습니다.
> - Claude: `args: ["--permission-mode", "auto"]`
> - Aider: `args: ["--yes-always"]`

---

## 4단계: 작업 명세(`workflow.yaml`) 작성

실제 수행할 비즈니스 작업, 단계별 입출력 아티팩트 전달, 실행 조건 등을 정의합니다.

### 작성 예시 (`mission.yaml`)
```yaml
version: "0.4.0"
name: "implement-healthcheck-feature"

# 3단계에서 작성한 AI 팀 명세 파일 지정
agents_file: "my_team.yaml"

workflow:
  topology: "pipeline"      # pipeline(순차 릴레이) 또는 conductor, debate
  timeout_per_step: 300     # 스텝당 최대 제한 시간(초)
  steps:
    # 스텝 1: 아키텍트가 기획서 작성
    - id: "step_plan"
      agent: "architect"
      instruction: "Write a technical specification for adding a /healthz endpoint."
      output_artifact: "health_spec.md"

    # 스텝 2: 개발자가 기획서를 읽고 코드 구현
    - id: "step_code"
      agent: "developer"
      condition: "artifact_exists:health_spec.md"  # 선행 산출물 확인
      input_artifacts: ["health_spec.md"]         # 기획서 내용 자동 주입
      instruction: "Read health_spec.md and implement the /healthz endpoint in app.py."
      output_artifact: "app.py"
      retry_count: 1                              # 실패 시 1회 재시도
      fallback_agent: "architect"                 # 재시도 실패 시 아키텍트에 대체 위임

    # 스텝 3: 리뷰어가 코드 검토 (사용자 승인 체크포인트)
    - id: "step_review"
      agent: "reviewer"
      input_artifacts: ["health_spec.md", "app.py"]
      instruction: "Review the implementation in app.py against health_spec.md."
      output_artifact: "review.md"
```

---

## 5단계: 실행 및 상태 점검

### 1. 공용 칠판(Blackboard) 초기화 (선택 사항)
```bash
PYTHONPATH=src python3 -m modue_harness.cli init
```

### 2. 워크플로우 실행
```bash
# 기본 실행
PYTHONPATH=src python3 -m modue_harness.cli run --config mission.yaml

# 실행 보고서(Markdown) 자동 생성
PYTHONPATH=src python3 -m modue_harness.cli run --config mission.yaml --report report.md

# 다른 AI 팀 명세로 교체하여 실행 (오버라이드)
PYTHONPATH=src python3 -m modue_harness.cli run --config mission.yaml --agents local_team.yaml
```

### 3. 진행 상황 및 산출물 확인
```bash
# 전체 세션 및 태스크 상태 조회
PYTHONPATH=src python3 -m modue_harness.cli status
```

생성된 파일은 프로젝트 내 `blackboard/` 폴더에서 바로 확인하실 수 있습니다:
- `blackboard/artifacts/`: AI 에이전트들이 생성한 기획서, 코드, 보고서 등
- `blackboard/logs/`: 각 AI CLI의 상세 원시 실행 로그
- `blackboard/state.json`: 현재 워크플로우 실행 메트릭

---

## 6단계: 트러블슈팅 및 자주 묻는 질문 (FAQ)

### Q1. AI CLI 프로세스가 아무 출력 없이 멈춰 있어요.
- **원인**: AI CLI가 사용자 승인(Y/N) 입력을 대기하고 있을 가능성이 높습니다.
- **해결책**:
  - Claude: `agents.yaml`의 `args`에 `["--permission-mode", "auto"]` 추가
  - Aider: `args`에 `["--yes-always"]` 추가
  - `workflow.yaml` 스텝에 `stall_timeout: 60`을 설정하여 무응답 시 자동 감지 및 중단 유도

### Q2. `Command not found: 'claude'` (종료 코드 127) 오류가 납니다.
- **원인**: 해당 CLI 명령어가 시스템 `PATH`에 등록되어 있지 않습니다.
- **해결책**:
  - 터미널에서 `which claude`를 실행하여 경로 확인 (예: `/usr/local/bin/claude`)
  - `agents.yaml`에서 절대 경로 지정:
    ```yaml
    command: "/usr/local/bin/claude"
    ```

### Q3. AI 에이전트가 기존 코드를 함부로 덮어쓸까 봐 불안합니다.
- **해결책 (Git Worktree 격리 모드 사용)**:
  `workflow.yaml` 스텝에 `isolation: "worktree"`를 지정하면, 임시 Git 브랜치 워크트리에서 코드를 수정한 뒤 검증하므로 메인 작업 트리가 안전하게 보호됩니다.

### Q4. API 비용이나 무한 루프가 걱정됩니다.
- **해결책**: ModueHarness의 `ProcessSupervisor`가 동일한 에러나 텍스트가 20회 이상 반복 출력되면 무한 루프로 판단하고 프로세스를 강제 종료(`SIGKILL`)합니다. 또한 `timeout_per_step`을 통해 최대 실행 시간을 제어할 수 있습니다.
