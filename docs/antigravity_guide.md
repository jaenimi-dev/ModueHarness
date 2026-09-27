# Google Antigravity (AGY) 연동 가이드 (Antigravity Integration Guide)

Google Deepmind의 에이전틱 AI 코딩 CLI 도구인 **Google Antigravity (`agy`)**를 ModueHarness와 연동하여 자율 협업 엔지니어링 팀을 구성하고 활용하는 종합 가이드입니다.

---

## 📌 목차
1. [Google Antigravity (AGY) 개요](#1-google-antigravity-agy-개요)
2. [설치 및 바이너리 확인](#2-설치-및-바이너리-확인)
3. [인증 (Authentication)](#3-인증-authentication)
4. [핵심 CLI 플래그 및 연동 원리](#4-핵심-cli-플래그-및-연동-원리)
5. [지원 모델 및 추론 노력(Effort)](#5-지원-모델-및-추론-노력effort)
6. [ModueHarness 연동 방법 3가지](#6-modueharness-연동-방법-3가지)
7. [Claude + Antigravity 하이브리드 팀 구성](#7-claude--antigravity-하이브리드-팀-구성)
8. [트러블슈팅](#8-트러블슈팅)

---

## 1. Google Antigravity (AGY) 개요

**Antigravity CLI (`agy`)**는 터미널 환경에서 소스코드 생성, 수정, 테스트, 터미널 명령 실행 등을 자율적으로 수행하는 Google의 차세대 AI 코딩 에이전트입니다.

### 주요 특징
* **다양한 고성능 모델**: `gemini-3.8-flash-high`, `gemini-3.1-pro-high`, `claude-sonnet-4-6` 등 최신 모델 탑재
* **추론 노력(Reasoning Effort)**: `low`, `medium`, `high` 지원
* **단일 실행 모드 (`-p`, `--print`)**: 프롬프트를 비대화형으로 즉시 실행하고 터미널에 결과를 반환하여 파이프라인 연동에 최적화

---

## 2. 공식 설치 방법 (OS별)

공식 웹페이지([Getting Started - CLI](https://antigravity.google/docs/getting-started?tab=cli#tab-panel-83))에 안내된 OS별 공식 Fast-Path 설치 명령어입니다:

### 1) macOS / Linux
터미널을 열고 다음 스크립트를 실행합니다:
```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
```
* **기본 설치 위치**: `~/.local/bin/agy`
* **PATH 등록 확인**: 설치 후 터미널에서 `agy` 명령어가 실행되지 않으면 `~/.bashrc` 또는 `~/.zshrc`에 다음 줄을 추가합니다:
  ```bash
  export PATH="$HOME/.local/bin:$PATH"
  ```

### 2) Windows (PowerShell)
PowerShell을 실행하고 다음 명령어를 실행합니다:
```powershell
irm https://antigravity.google/cli/install.ps1 | iex
```
* **기본 설치 위치**: `C:\Users\<username>\AppData\Local\agy\bin` (또는 `%LOCALAPPDATA%\agy\bin`)
* **PATH 자동 등록**: 설치 스크립트가 사용자 환경 변수(Registry) `Path`에 해당 디렉터리를 자동 등록합니다.
* **⚠️ 주의 (PATH 반영 안내)**:
  - 이미 열려 있는 기존 터미널 창에는 변경된 시스템 환경 변수가 즉시 반영되지 않아 `Warning: ... is not present in your active Environment PATH` 경고가 표시됩니다.
  - **터미널 재시작**: 열려 있는 터미널(또는 VS Code)을 완전히 닫고 다시 열면 자동으로 정상 인식됩니다.
  - **현재 창에서 즉시 적용**: 터미널을 닫지 않고 바로 적용하려면 현재 PowerShell 창에 아래 명령을 실행합니다:
    ```powershell
    $env:Path += ";$env:LOCALAPPDATA\agy\bin"
    ```

### 3) Windows (CMD / 명령 프롬프트)
기본 명령 프롬프트(CMD)를 사용할 경우:
```batch
curl -fsSL https://antigravity.google/cli/install.cmd -o install.cmd && install.cmd && del install.cmd
```

### 4) 설치 및 버전 확인
```bash
agy --version
# 정상 출력 예: agy version 0.x.x
```

---

## 3. 인증 (Authentication) 및 초기 설정

### 1) 기본 대화형 계정 로그인 (권장)
터미널에서 `agy`를 실행합니다:
```bash
agy
```
1. **첫 실행 환경 설정**: 테마(Color Scheme: Dark/Solarized 등)와 렌더링 모드(Alt-Screen / Inline), 작업 디렉터리 신뢰(Workspace Trust)를 순서대로 선택합니다.
2. **브라우저 인증**: 기본 브라우저가 열리면 승인된 Google 계정으로 로그인을 완료합니다. 인증 토큰은 로컬 OS 키체인(Keychain / Secret Service / Credential Manager)에 안전하게 저장됩니다.
3. 인증이 완료되면 `/exit` 또는 `Ctrl+D`를 눌러 세션을 종료합니다. 이후 ModueHarness가 백그라운드에서 자동으로 인증된 세션을 활용합니다.

### 2) 원격 SSH 환경 인증
원격 서버에 SSH로 접속하여 `agy`를 실행하면 브라우저를 직접 열 수 없으므로, 터미널에 고유 인증 URL이 표시됩니다:
1. 터미널에 출력된 URL을 복사하여 로컬 PC 브라우저에 붙여넣고 로그인합니다.
2. 브라우저에 표시된 인증 코드를 복사하여 원격 터미널 프롬프트에 입력합니다.

### 3) Gemini API 키 사용 (CI/CD 및 헤드리스 환경)
브라우저 로그인 없이 Google AI Studio에서 발급받은 Gemini API 키로 실행할 수도 있습니다:
1. `~/.gemini/antigravity-cli/settings.json` 생성 또는 수정:
   ```json
   {
     "modelProvider": "gemini"
   }
   ```
2. 환경 변수 설정:
   ```bash
   export GEMINI_API_KEY="your-api-key"
   ```
   (Windows PowerShell: `$env:GEMINI_API_KEY="your-api-key"`)

---

## 4. 핵심 CLI 플래그 및 연동 원리

ModueHarness는 `AGYCLIAdapter`를 통해 하위 서브프로세스로 `agy`를 호출합니다:

| 옵션 | 설명 | ModueHarness 자동 처리 |
| :--- | :--- | :--- |
| `-p`, `--print` | 일회성 프롬프트 실행 후 결과 반환 (비대화형 모드) | `prompt_delivery="flag"`로 자동 전달 |
| `--dangerously-skip-permissions` | 도구 실행 및 파일 편집 시 사용자 승인 대기 없이 자동 실행 | `skip_permissions=True` (기본값)로 자동 포함 (파이프라인 스톨 방지) |
| `--sandbox` | 터미널 명령을 샌드박스에서 실행 (쓰기는 작업 폴더·임시 폴더만, 네트워크 차단) | `sandbox=True` (macOS/Linux 기본값, Windows는 Preview라 기본 off) |
| `--model` | 세션에서 사용할 AI 모델 지정 | `--model <모델명>` 인자로 자동 전달 |
| `--effort` | 생각/추론 노력 깊이 조절 (`low`, `medium`, `high`) | `--effort <레벨>` 인자로 자동 전달 |

### 작업 폴더 밖 쓰기 차단 (agy-guard)

`--dangerously-skip-permissions`로 실행하면 agy의 `allowNonWorkspaceAccess`(기본 off)가 무시되어, **파일 도구가 프로젝트 폴더 밖에도 씁니다.** `--sandbox`는 터미널 명령만 막고 파일 도구는 막지 못합니다. agy 1.2.11로 직접 확인한 동작은 다음과 같습니다.

| 실행 방식 | 파일 도구로 밖에 쓰기 | 셸로 밖에 쓰기 |
| :--- | :--- | :--- |
| `--dangerously-skip-permissions` | 씀 | 씀 |
| + `--sandbox` | **씀** | 차단 |
| + `--sandbox` + deny 규칙 (자동 설치, 하네스 기본값) | 차단 | 차단 |

agy의 deny 규칙은 `--dangerously-skip-permissions`보다 우선합니다. 하네스는 **agy 에이전트를 실행하기 직전에** 하네스 저장소의 최상위 항목(`projects/`, `blackboard/` 제외)과 민감한 홈 경로(`~/.ssh`, `~/.bashrc` 등)에 대한 deny 규칙이 `~/.gemini/antigravity-cli/settings.json`의 `permissions.deny`에 있는지 확인하고, 빠진 규칙을 자동으로 추가합니다.

* 규칙을 처음 추가할 때 한 번 안내 메시지를 출력하고, 원래 설정은 `settings.json.modue-backup`으로 백업합니다(백업은 최초 1회만 생성).
* 실행할 때마다 규칙을 다시 계산하므로, 저장소에 새로 만든 최상위 파일·폴더도 다음 실행부터 보호됩니다.
* 실행 위치가 작업 폴더를 포함하지 않거나 홈 폴더(또는 그 상위)인 경우에는 agy 자신의 폴더까지 막을 수 있어 자동 설치를 건너뜁니다.
* 설정 파일이 손상되어 규칙을 넣을 수 없으면 보호 없이 실행하지 않고 해당 턴을 실패로 처리합니다.
* 자동 설치를 원하지 않으면 에이전트에 `write_guard: false`를 지정하세요. 이 경우 규칙이 없으면 시작할 때 경고가 표시됩니다.

규칙은 다음 명령으로 직접 확인하거나 제거할 수 있습니다. 하네스 저장소 루트에서 실행하세요.

```bash
modue-harness agy-guard            # 설치 상태 확인 (기본 동작)
modue-harness agy-guard install    # 규칙 추가 (기존 설정은 settings.json.modue-backup 으로 백업)
modue-harness agy-guard uninstall  # 하네스가 추가한 규칙만 제거
```

* agy 규칙 우선순위가 Deny > Ask > Allow라서 "작업 폴더 밖 전부"를 막을 수는 없습니다. 목록에 없는 경로(예: 하네스 저장소 밖의 다른 폴더)는 여전히 보호되지 않습니다.
* `skip_permissions: false`로 실행하면 비대화형 모드에서 쓰기가 전부 자동 거부되고 턴이 중단됩니다. agy는 이때도 종료 코드 0을 내지만, 하네스는 이를 실패로 처리합니다.

---

## 5. 지원 모델 및 추론 노력(Effort)

`agy models` 명령으로 현재 사용 가능한 모델 목록을 조회할 수 있습니다:

### 주요 모델
* `gemini-3.8-flash-high` *(추천: 초고속 및 높은 코딩 능력)*
* `gemini-3.7-flash-high`
* `gemini-3.1-pro-high` *(심층 추론 및 복잡한 설계)*
* `claude-sonnet-4-6`

### 추론 노력 레벨 (`--effort`)
* `low`: 단순 스크립트 작성 및 빠른 응답
* `medium`: 기본 균형 모드
* `high` *(권장)*: 심층 아키텍처 분석, 복잡한 비즈니스 로직 및 테스트 설계

---

## 6. ModueHarness 연동 방법 3가지

### 방법 1: CLI 실행 시 `--agent agy` 지정 (가장 빠른 실행)
별도의 설정 파일 없이 시스템에 설치된 Antigravity를 즉시 사용하여 대화형 세션이나 단일 작업을 수행합니다:

```bash
# Antigravity 단독 대화형 모드 실행
python run.py -i -P my-web-app --agent agy

# 특정 모델과 추론 노력을 함께 지정
python run.py -i -P my-web-app --agent agy --model gemini-3.8-flash-high --effort high

# 단일 명령 직접 실행
python run.py "FastAPI 기반 REST API 엔드포인트와 pytest 테스트 작성" -P my-api --agent agy
```
> `agy`와 `antigravity` 별칭 모두 지원합니다.

---

### 방법 2: 대화형 REPL 세션 중 실시간 모델/노력 변경
대화형 모드 실행 중 슬래시 명령어로 Antigravity 모델과 추론 노력을 즉시 조회하고 변경할 수 있습니다:

```text
[my-web-app] > /model
[my-web-app] > /model gemini-3.8-flash-high
[my-web-app] > /effort high
[my-web-app] > /effort developer medium
```

---

### 방법 3: `config/agents.yaml`에 Antigravity 팀 구성 (영구 설정)
팀원 전체를 Antigravity로 구성하거나 역할을 분담할 수 있습니다:

```yaml
version: "0.6.0"
name: "antigravity-engineering-team"

agents:
  # 1. 아키텍트: 심층 추론 모델 사용
  architect:
    adapter: "antigravity"             # 또는 "agy"
    command: "agy"
    model: "gemini-3.8-flash-high"
    effort: "high"
    role: "System Architect"
    system_instruction: "You design clean, modular software architecture specifications."

  # 2. 소프트웨어 엔지니어: 고속 구현
  developer:
    adapter: "antigravity"
    command: "agy"
    model: "gemini-3.8-flash-high"
    effort: "medium"
    role: "Core Implementation Engineer"
    system_instruction: "You write production-ready, clean code in the project directory."

  # 3. 품질 & 테스트 리뷰어
  reviewer:
    adapter: "antigravity"
    command: "agy"
    model: "gemini-3.8-flash-high"
    effort: "high"
    role: "Quality Assurance & Reviewer"
    system_instruction: "You thoroughly review code, edge cases, and run tests."
```

---

## 7. Claude + Antigravity 하이브리드 팀 구성

Claude Code와 Antigravity의 장점을 조합한 **드림팀**을 손쉽게 구성할 수 있습니다:
* **기획/설계(Architect)**: Claude 3.7 Sonnet (깊은 논리적 분석 및 아키텍처)
* **코드 구현(Developer)**: Google Antigravity Gemini Flash (초고속 코드 생성 및 도구 활용)
* **품질 검증(Reviewer)**: Claude 3.7 Sonnet (엄격한 엣지케이스 및 보안 리뷰)

```yaml
version: "0.6.0"
name: "hybrid-ai-team"

agents:
  architect:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]
    model: "claude-3-7-sonnet-latest"
    effort: "high"

  developer:
    adapter: "antigravity"
    command: "agy"
    args: ["--dangerously-skip-permissions"]
    model: "gemini-3.8-flash-high"
    effort: "medium"

  reviewer:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]
    model: "claude-3-7-sonnet-latest"
    effort: "high"
```

---

## 8. 트러블슈팅

### Q1. `agy` 명령을 찾을 수 없다는 오류가 발생합니다.
* ModueHarness는 시스템 `PATH` 외에도 다음 위치의 실행 파일을 자동으로 탐색합니다:
  - **macOS / Linux**: `~/.local/bin/agy`, `~/.gemini/antigravity-cli/bin/agy`, `/usr/local/bin/agy`, `/usr/bin/agy`
  - **Windows**: `%LOCALAPPDATA%\agy\bin\agy.exe`, `C:\Users\<username>\AppData\Local\agy\bin\agy.exe`
* 만약 다른 특수 경로에 설치되어 있다면, `agents.yaml`에서 `command: "/절대경로/agy"`로 지정하거나 셸의 `PATH`에 등록하세요:
  - Linux/macOS:
    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    ```
  - Windows PowerShell:
    ```powershell
    $env:Path += ";$env:LOCALAPPDATA\agy\bin"
    ```

### Q2. Antigravity가 사용자 입력을 기다리며 멈춥니다.
* `AGYCLIAdapter`는 기본적으로 `--dangerously-skip-permissions` 플래그를 자동으로 추가하여 사용자 확인 팝업 없이 작업을 자율 진행합니다.
* 수동으로 `command`나 `args`를 재정의할 때도 `--dangerously-skip-permissions`를 포함해 주세요.

### Q. 샌드박스 때문에 `pip install`이나 네트워크가 필요한 명령이 실패합니다.
* `--sandbox`는 터미널 명령의 네트워크를 차단합니다. 필요한 에이전트에만 `agents.yaml`에서 `sandbox: false`를 지정하세요. 이 경우 셸 명령은 작업 폴더 밖에도 쓸 수 있습니다.
