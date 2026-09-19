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

## 2. 설치 및 바이너리 확인

### 설치 경로
Antigravity는 일반적으로 사용자 홈 디렉터리에 설치됩니다:
* `~/.local/bin/agy`
* `~/.gemini/antigravity-cli/bin/`

ModueHarness는 시스템 `PATH`뿐만 아니라 위 로컬 설치 경로(`~/.local/bin/agy` 등)를 **자동 탐색**하여 인식하므로, 별도의 복잡한 PATH 설정 없이도 바로 실행할 수 있습니다.

### 설치 및 버전 확인
```bash
agy --version
# 또는 전체 경로로 확인
~/.local/bin/agy --version
```

---

## 3. 인증 (Authentication)

Antigravity CLI를 처음 실행할 때 Google 계정 인증을 진행합니다:
```bash
agy
```
화면에 나타나는 브라우저 링크 및 OAuth 인증 절차를 완료하면 자격 증명이 로컬에 안전하게 저장됩니다. 인증 완료 후 `/exit` 또는 `Ctrl+D`를 눌러 세션을 종료하면, 이후 ModueHarness가 백그라운드에서 자동으로 Antigravity를 호출합니다.

---

## 4. 핵심 CLI 플래그 및 연동 원리

ModueHarness는 `AGYCLIAdapter`를 통해 하위 서브프로세스로 `agy`를 호출합니다:

| 옵션 | 설명 | ModueHarness 자동 처리 |
| :--- | :--- | :--- |
| `-p`, `--print` | 일회성 프롬프트 실행 후 결과 반환 (비대화형 모드) | `prompt_delivery="flag"`로 자동 전달 |
| `--dangerously-skip-permissions` | 도구 실행 및 파일 편집 시 사용자 승인 대기 없이 자동 실행 | `skip_permissions=True` (기본값)로 자동 포함 (파이프라인 스톨 방지) |
| `--model` | 세션에서 사용할 AI 모델 지정 | `--model <모델명>` 인자로 자동 전달 |
| `--effort` | 생각/추론 노력 깊이 조절 (`low`, `medium`, `high`) | `--effort <레벨>` 인자로 자동 전달 |

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
version: "0.5.0"
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
version: "0.5.0"
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
* ModueHarness는 `~/.local/bin/agy`와 `~/.gemini/antigravity-cli/bin/agy` 경로를 자동으로 탐색합니다.
* 만약 다른 특수 경로에 설치되어 있다면, `agents.yaml`에서 `command: "/절대경로/agy"`로 지정하거나 셸의 `PATH`에 등록하세요:
  ```bash
  export PATH="$HOME/.local/bin:$PATH"
  ```

### Q2. Antigravity가 사용자 입력을 기다리며 멈춥니다.
* `AGYCLIAdapter`는 기본적으로 `--dangerously-skip-permissions` 플래그를 자동으로 추가하여 사용자 확인 팝업 없이 작업을 자율 진행합니다.
* 수동으로 `command`나 `args`를 재정의할 때도 `--dangerously-skip-permissions`를 포함해 주세요.
