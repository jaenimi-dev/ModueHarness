# Claude Code 연동 및 퀵스타트 가이드 (Claude Code Integration Guide)

Anthropic의 공식 [Claude Code 빠른 시작(Quickstart) 가이드](https://code.claude.com/docs/ko/quickstart) 내용을 바탕으로, **Claude Code를 단독으로 사용하는 기본 방법**부터 **ModueHarness 멀티 에이전트 오케스트레이션에 연동하여 자율 협업 팀을 구축하는 실전 방법**까지 정리한 종합 매뉴얼입니다.

---

## 📌 목차
1. [Claude Code 개요 및 요구 사항](#1-claude-code-개요-및-요구-사항)
2. [공식 설치 방법 (OS별)](#2-공식-설치-방법-os별)
3. [계정 로그인 및 인증](#3-계정-로그인-및-인증)
4. [핵심 실행 모드 및 필수 명령어](#4-핵심-실행-모드-및-필수-명령어)
5. [권한 모드(Permission Modes)와 ModueHarness 자동화](#5-권한-모드permission-modes와-modueharness-자동화)
6. [프롬프팅 모범 사례 및 워크플로우](#6-프롬프팅-모범-사례-및-워크플로우)
7. [프로젝트 규칙 정의 (`CLAUDE.md`)](#7-프로젝트-규칙-정의-claudemd)
8. [ModueHarness 실전 연동 예제](#8-modueharness-실전-연동-예제)
9. [트러블슈팅 (FAQ)](#9-트러블슈팅-faq)

---

## 1. Claude Code 개요 및 요구 사항

**Claude Code**는 터미널 CLI 환경에서 동작하며, 개발자의 코드베이스를 직접 읽고 수정하고 테스트와 Git 명령어를 실행할 수 있는 에이전틱 AI 코딩 어시스턴트입니다.

### 사전 준비 사항
- **터미널 환경**: macOS, Linux, WSL(Windows Subsystem for Linux), 또는 Windows (CMD / PowerShell)
- **Git**: 코드 버전 관리 (Windows 기본 환경의 경우 Git for Windows 권장)
- **계정/플랜 (아래 중 택일)**:
  - Claude 구독 (Pro, Max, Team, Enterprise) — *권장*
  - [Claude Console](https://platform.claude.com/) 계정 (선불 크레딧 기반 API 키)
  - 엔터프라이즈 클라우드 (Amazon Bedrock, Google Cloud Agent Platform, Microsoft Foundry)

---

## 2. 공식 설치 방법 (OS별)

Anthropic에서는 백그라운드 자동 업데이트가 지원되는 **공식 네이티브 설치 스크립트**를 가장 권장합니다.

### 1) 기본 권장 설치 (자동 업데이트 지원)
- **macOS, Linux, WSL**:
  ```bash
  curl -fsSL https://claude.ai/install.sh | bash
  ```
- **Windows PowerShell**:
  ```powershell
  irm https://claude.ai/install.ps1 | iex
  ```
  > 💡 **Windows PATH 환경 변수 자동 등록 (중요)**:  
  > 설치 후 `... \.local\bin is not in your PATH` 알림이 뜨면 특정 사용자 계정명에 구애받지 않는 범용 환경 변수(`$HOME` 또는 `%USERPROFILE%`)를 사용하여 등록합니다:
  > - **PowerShell 명령어 (추천)**:
  >   ```powershell
  >   $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  >   [Environment]::SetEnvironmentVariable("Path", "$userPath;$HOME\.local\bin", "User")
  >   $env:Path += ";$HOME\.local\bin"
  >   ```
  > - **Windows GUI 수동 등록**:
  >   `Win + R` → `sysdm.cpl` 실행 → [고급] → [환경 변수] → 사용자 변수의 `Path` 편집 → [새로 만들기] → `%USERPROFILE%\.local\bin` 입력 후 저장 및 터미널 재시작

- **Windows CMD**:
  ```batch
  curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
  ```

### 2) 패키지 매니저를 통한 설치
- **Homebrew (macOS/Linux)**:
  ```bash
  # 안정 버전 채널
  brew install --cask claude-code

  # 최신 릴리스 즉시 반영 채널
  brew install --cask claude-code@latest
  ```
  *(참고: Homebrew 설치본은 `brew upgrade claude-code`로 수동 업데이트해야 합니다)*
- **WinGet (Windows)**:
  ```powershell
  winget install Anthropic.ClaudeCode
  ```
- **Linux 패키지 매니저 (apt, dnf, apk)**:
  Debian, Fedora, RHEL, Alpine 환경 지원
- **npm (대체 방식)**:
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```

### 3) 설치 확인
```bash
claude --version
# 정상 출력 예시: 2.1.239 (Claude Code)
```

---

## 3. 계정 로그인 및 인증

Claude Code는 터미널 세션 또는 환경 변수를 통해 계정을 인증합니다.

### 방법 A: 대화형 브라우저 로그인 (Pro, Max, Team 권장)
터미널에서 `claude`를 실행하면 최초 1회 로그인 안내가 나타납니다:
```bash
claude
```
1. 브라우저가 열리면 Anthropic 계정 로그인을 완료합니다.
2. 로그인이 완료되면 터미널에 첫 작업 안내나 온보딩 선택지가 나타납니다.
3. 이때 **`No, exit`를 선택하거나 `/exit`를 입력하여 세션을 바로 종료하셔도 됩니다.** 브라우저 로그인 시점에 인증 자격 증명이 로컬에 이미 안전하게 저장되었으므로, 이후 ModueHarness가 자동으로 Claude를 호출하여 작업을 수행합니다.
*(세션 내에서 계정을 변경하거나 재인증하려면 `/login`을 입력합니다)*

### 방법 B: API 키 직접 설정 (`ANTHROPIC_API_KEY`)
Claude Console API 키를 사용하는 경우, 환경 변수로 설정해 두면 브라우저 로그인 절차 없이 자동으로 인증됩니다:
```bash
# 터미널 또는 .env 파일에 등록
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```
> 💡 **참고**: 방법 A(브라우저 로그인)로 인증한 경우 로컬 토큰을 사용하므로 `.env` 파일이 필요 없습니다. Console API 키(방법 B)를 사용할 경우에만 프로젝트 루트의 `.env` 파일에 키를 등록하면 ModueHarness가 자동으로 하위 `claude` 프로세스에 전달합니다.

---

## 4. 핵심 실행 모드 및 필수 명령어

### 1) 셸 명령어 (Terminal Shell Commands)
| 명령어 | 동작 설명 | 활용 시점 |
| :--- | :--- | :--- |
| `claude` | 대화형(Interactive) 대화 세션 시작 | 실시간 페어 프로그래밍 |
| `claude "task"` | 초기 프롬프트와 함께 대화형 세션 시작 | 특정 목표를 가지고 세션 진입 |
| `claude -p "query"` | **비인터랙티브 일회성 쿼리 실행 후 즉시 종료 (Print 모드)** | **ModueHarness 파이프라인 연동 시 핵심** |
| `claude -c` | 현재 디렉터리에서 가장 최근 대화 계속 | 이전 세션 문맥 유지 |
| `claude -r` | 이전 대화 목록에서 선택 재개 | 과거 작업 복구 |

### 2) 세션 내 단축 명령어 (Session Commands)
대화형 세션 안에서 입력하는 명령어입니다:
- `/help`: 사용 가능한 명령어 및 단축키 목록
- `/clear`: 현재 대화 문맥 초기화
- `/login`: 계정 변경 및 재인증
- `Shift+Tab`: 권한 모드(Manual ↔ Auto) 즉시 전환
- `/exit` (또는 `Ctrl+D` 2회): 세션 종료

---

## 5. 권한 모드(Permission Modes)와 ModueHarness 자동화

Claude Code는 코드 수정 및 셸 명령어 실행 시 보안을 위해 권한 모드를 제공합니다.

### 1) 권한 모드 종류
- **Auto (자동 모드)**: Pro/Max/Team 플랜의 기본값. 내장 분류기가 안전성을 검토하며, 대부분의 파일 수정 및 명령어를 **사용자에게 묻지 않고 자동 실행**합니다.
- **Manual (수동 모드)**: 파일을 편집하거나 명령어를 실행하기 전마다 사용자에게 "예/아니오" 승인을 요청합니다.

### 2) ModueHarness 연동 시 주의점 (스톨 방지!)
ModueHarness는 백그라운드 서브프로세스로 AI CLI를 실행합니다. 만약 Claude Code가 "파일을 수정하시겠습니까? (Y/N)" 프롬프트를 띄우고 대기하면 파이프라인이 멈추게(Stall) 됩니다.

따라서 `agents.yaml`에 Claude를 등록할 때는 **반드시 `--permission-mode auto` 인자를 지정**해야 합니다:

```yaml
agents:
  claude_agent:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]  # 승인 대기 없이 자동 실행 보장
```

### 3) 모델(Model) 및 생각/추론 노력(Effort) 설정
Claude Code 2.1+ (Claude 3.7 Sonnet 등)는 문제 해결 시 내부 숙고를 얼마나 깊게 할지 결정하는 **추론 노력(Reasoning Effort)** 기능을 지원합니다.

- **모델 지정 (`--model`)**:
  - `claude-3-7-sonnet-latest`, `sonnet`, `opus`, `haiku`
- **추론 노력 지정 (`--effort`)**:
  - `low`: 빠른 응답, 단순 문법 수정 및 스크립트 작성에 적합 (비용/시간 절약)
  - `medium`: 기본 균형 모드
  - `high`: 복잡한 아키텍처 설계, 동시성/보안/알고리즘 문제에 적합 (권장)
  - `xhigh` / `max`: 최고 수준의 심층 추론

#### ModueHarness에서 설정하는 3가지 방법
1. **`agents.yaml` 명세 파일에서 에이전트별로 설정**:
   ```yaml
   agents:
     architect:
       adapter: "claude"
       model: "claude-3-7-sonnet-latest"
       effort: "high"   # 아키텍트는 깊이 생각하도록 설정
     developer:
       adapter: "claude"
       model: "claude-3-7-sonnet-latest"
       effort: "medium" # 구현 엔지니어는 신속하게 코드 작성
   ```
2. **CLI 실행 시 명령행 옵션 지정**:
   ```bash
   python run.py -i -P my-web-app --model sonnet --effort high
   ```
3. **대화형 REPL 세션 중 슬래시 명령어로 실시간 변경**:
   ```text
   [my-web-app] > /model sonnet
   [my-web-app] > /effort high
   [my-web-app] > /effort architect max
   ```

---

## 6. 프롬프팅 모범 사례 및 워크플로우

공식 빠른 시작 가이드에서 권장하는 효과적인 프롬프팅 기법입니다.

### 1) 요청을 구체적으로 하기 (Be Specific)
- ❌ 피해야 할 예시: `"버그 수정해줘"`
- ⭕ 권장 예시: `"로그인 폼에서 공백 문자를 입력하고 제출했을 때 500 에러 대신 클라이언트 유효성 검사 에러를 띄우도록 수정해줘"`

### 2) 단계별 지침 사용 (Step-by-Step Instructions)
복잡한 작업을 한 번에 요청하기보다 논리적 순서로 분할합니다:
```text
1. User 모델에 email_verified 컬럼 추가 (마이그레이션 생성)
2. 회원가입 시 인증 이메일 발송 큐 로직 추가
3. 이메일 토큰 검증 API 엔드포인트(/auth/verify-email) 구현
```
> 💡 **ModueHarness 팁**: 이 단계를 `workflow.yaml`의 `steps`로 쪼개어 각각 설계자(Claude), 구현자(Claude/AGY), 리뷰어(Claude)에게 분담시키면 환각이 줄어들고 결과물이 완벽해집니다.

### 3) 탐색 우선 (Read/Explore First)
Claude Code는 프로젝트의 코드 구조를 스스로 탐색할 수 있습니다. 바로 코드를 고치게 하기보다 먼저 아키텍처나 관련 모듈을 파악하게 하면 실수를 방지할 수 있습니다:
```text
"먼저 현재 인증 흐름과 세션 관리 구조를 분석하고, 그 결과를 markdown으로 정리해줘"
```

---

## 7. 프로젝트 규칙 정의 (`CLAUDE.md`)

Claude Code는 작업 디렉터리에 `CLAUDE.md` 파일이 존재하면 이를 읽고 프로젝트 컨벤션과 규칙을 스스로 준수합니다.

### 추천 `CLAUDE.md` 템플릿
ModueHarness 프로젝트 루트 또는 서브 프로젝트에 아래와 같이 `CLAUDE.md`를 배치해 두면, Claude가 항상 일관된 코딩 스타일과 ModueHarness 규약을 준수합니다:

```markdown
# 프로젝트 규칙 (CLAUDE.md)

## 일반 원칙
- Python 3.9+ 호환성 유지, PEP 8 준수
- 모든 공개 함수와 클래스에 명확한 타입 힌트와 독스트링 작성
- 모든 커밋 메시지와 산출물 주석은 한글을 우선 사용

## ModueHarness 연동 규약
- 생성된 결과물 및 문서는 `blackboard/artifacts/`에 저장할 것
- 중간 진행 상황이나 진단 내용은 `blackboard/logs/`에 기록할 것
```

---

## 8. ModueHarness 실전 연동 예제

Claude Code 하나만으로도 역할을 분리하여 **기획자(Architect) - 엔지니어(Developer) - 리뷰어(Reviewer)** 3인 협업 팀을 구축할 수 있습니다.

### 1) AI 팀 명세: `claude_team.yaml`
```yaml
version: "0.6.0"
name: "claude-all-stars"

agents:
  # 설계 및 기획 에이전트 (깊은 심층 추론)
  architect:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]
    model: "claude-3-7-sonnet-latest"
    effort: "high"
    role: "System Architect"
    system_instruction: "You are a software architect. Focus on clean interfaces, SOLID principles, and modular designs."

  # 구현 에이전트 (빠르고 정확한 구현)
  developer:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]
    model: "claude-3-7-sonnet-latest"
    effort: "medium"
    role: "Software Implementation Engineer"
    system_instruction: "You write production-quality, tested code matching the architectural specifications."

  # 품질 및 보안 검토 에이전트 (빈틈없는 엣지케이스 검토)
  reviewer:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]
    model: "claude-3-7-sonnet-latest"
    effort: "high"
    role: "Code & Security Reviewer"
    system_instruction: "You critically review code for edge cases, performance bottlenecks, and security vulnerabilities."
```

### 2) 작업 워크플로우 명세: `feature_pipeline.yaml`
```yaml
version: "0.6.0"
name: "build-token-bucket-ratelimiter"
agents_file: "claude_team.yaml"

workflow:
  topology: "pipeline"
  timeout_per_step: 300
  steps:
    # 1단계: 아키텍트가 설계서 작성
    - id: "design"
      agent: "architect"
      instruction: "Design a thread-safe Token Bucket Rate Limiter class in Python. Save design notes."
      output_artifact: "rate_limiter_design.md"

    # 2단계: 개발자가 설계서를 주입받아 구현 및 테스트 작성
    - id: "implement"
      agent: "developer"
      condition: "artifact_exists:rate_limiter_design.md"
      input_artifacts: ["rate_limiter_design.md"]
      instruction: "Read rate_limiter_design.md and implement the RateLimiter in rate_limiter.py with unit tests."
      output_artifact: "rate_limiter.py"

    # 3단계: 리뷰어가 설계서와 구현 코드를 비교 검토
    - id: "review"
      agent: "reviewer"
      input_artifacts: ["rate_limiter_design.md", "rate_limiter.py"]
      instruction: "Review rate_limiter.py against rate_limiter_design.md and write a comprehensive review report."
      output_artifact: "review_report.md"
```

### 3) 실행 명령어

#### 방법 A. 자연어 대화형 또는 단일 명령 실행 (가장 간편, YAML 작성 불필요)
```bash
# 대화형 REPL 모드로 시작
python run.py -i -P rate-limiter

# 또는 단일 명령으로 즉시 Sonnet 모델 + 높은 추론 노력으로 실행
python run.py "토큰 버킷 기반 RateLimiter 모듈과 pytest 테스트를 작성해줘" -P rate-limiter -m sonnet -e high
```

#### 방법 B. 정적 워크플로우 명세 파일 실행
```bash
# [가장 간편] 루트 실행 파일 사용 (Windows / Mac / Linux 공통, 환경변수 불필요)
python run.py run --config feature_pipeline.yaml --report final_report.md

# [전용 CLI] pip install -e . 설치 후 사용
modue-harness run --config feature_pipeline.yaml --report final_report.md

# [모듈 직접 실행]
# Linux / macOS (Bash)
PYTHONPATH=src python3 -m modue_harness.cli run --config feature_pipeline.yaml --report final_report.md
# Windows PowerShell
$env:PYTHONPATH="src"; python -m modue_harness.cli run --config feature_pipeline.yaml --report final_report.md
```

실행이 완료되면 `blackboard/artifacts/`에 `rate_limiter_design.md`, `rate_limiter.py`, `review_report.md`가 순서대로 저장되며, 최종 요약본이 `final_report.md`로 생성됩니다.

---

## 9. 트러블슈팅 (FAQ)

### Q1. 프로세스가 멈추고 아무 출력이 나오지 않습니다.
- **원인**: Claude Code가 파일 편집 승인 대화상자나 확인 프롬프트를 띄운 채 대기 중일 수 있습니다.
- **해결책**:
  1. `agents.yaml`에 `args: ["--permission-mode", "auto"]`가 포함되어 있는지 확인합니다.
  2. `workflow.yaml` 스텝에 `stall_timeout: 60`을 설정하여 무응답 시 자동 인터럽트되도록 보호 장치를 겁니다.

### Q2. `curl` 설치 시 `403` 또는 `syntax error near unexpected token '<'` 에러가 발생합니다.
- **원인**: 방화벽이나 프록시, 또는 잘못된 셸 문법입니다.
- **해결책**:
  - macOS/Linux: `curl -fsSL https://claude.ai/install.sh | bash` 명령어가 온전히 복사되었는지 확인합니다.
  - 대안으로 `npm install -g @anthropic-ai/claude-code` 또는 `brew install --cask claude-code`를 사용합니다.

### Q3. Windows에서 `The token '&&' is not a valid statement separator` 오류가 납니다.
- **원인**: Windows CMD 전용 명령어를 PowerShell에서 실행했기 때문입니다.
- **해결책**:
  - PowerShell에서는 다음 명령어를 실행하십시오:
    ```powershell
    irm https://claude.ai/install.ps1 | iex
    ```

### Q4. Windows에서 설치 후 `... \.local\bin is not in your PATH` 알림이 뜹니다.
- **원인**: Claude Code 설치 파일(`claude.exe`)은 정상 다운로드되었으나, 윈도우 환경 변수 `Path`에 해당 디렉터리가 등록되지 않아 터미널이 `claude` 명령을 찾지 못하는 상태입니다.
- **해결책 (특정 사용자 계정명에 종속되지 않는 범용 등록 방법)**:
  - **방법 1 (PowerShell에서 1줄로 영구 등록, 추천)**:
    ```powershell
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$HOME\.local\bin", "User")
    $env:Path += ";$HOME\.local\bin"
    ```
  - **방법 2 (윈도우 그래픽 창 GUI 방식)**:
    1. `Win + R`을 누르고 `sysdm.cpl` 입력 후 엔터
    2. [고급] 탭 → [환경 변수(N)...] 클릭
    3. 사용자 변수 목록에서 `Path` 선택 후 [편집(E)...]
    4. [새로 만들기(N)] 클릭 후 아래 범용 환경 변수 경로 입력:
       ```text
       %USERPROFILE%\.local\bin
       ```
    5. [확인]을 눌러 저장하고, **새 터미널 창을 열어** `claude --version` 실행

### Q5. Claude의 컨텍스트 윈도우가 넘치거나 토큰 비용이 걱정됩니다.
- **해결책**:
  - ModueHarness의 `input_artifacts` 기능을 사용하여 이전 단계의 모든 출력이 아닌 **필요한 아티팩트만 선별하여 전달**하십시오.
  - 대화형 세션에서는 주기적으로 `/clear`를 실행하거나 파이프라인 방식(독립 프로세스)으로 각 스텝의 컨텍스트를 깔끔하게 유지합니다.
