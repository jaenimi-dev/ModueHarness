# ModueHarness (모두의 하네스)

[![Version](https://img.shields.io/badge/version-0.5.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-65%20passed-brightgreen.svg)](tests/)

**ModueHarness**는 Claude Code, Google Antigravity(AGY), Aider 등 다양한 AI CLI 도구들을 하나의 유기적인 팀으로 엮어 소프트웨어 엔지니어링 작업을 자율적·협업적으로 해결하는 Multi-AI CLI 하네스(Harness) 프레임워크입니다.

---

## 🚀 빠른 시작 (Quick Start)

### 1. 설치
```bash
git clone https://github.com/jaenimi-dev/ModueHarness.git
cd ModueHarness
pip install -e ".[dev]"
```

### 2. 테스트 검증
```bash
python3 -m pytest -q
# 62 passed in ~3.5s
```

### 3. CLI 실행 예시 (워크플로우 파일 없이 직접 명령 실행)

> 💡 **실행 방법 (아래 2가지 중 편한 방법 선택)**:
> - **방법 A (루트 실행 파일, 환경변수 불필요)**: `python run.py [옵션]`
> - **방법 B (전용 CLI 명령어, pip 설치 후)**: `modue-harness [옵션]`

```bash
# [추천] 대화형 CLI 모드 실행 (REPL)
python run.py -i -P my-web-app
# (또는 pip 설치 후: modue-harness -i -P my-web-app)

# Google Antigravity(AGY)를 지정하여 실행
python run.py -i -P my-web-app --agent agy -m gemini-3.8-flash-high -e high

# 단일 명령어로 즉시 프로젝트에 작업 구현
python run.py "FastAPI 기반 REST API와 테스트 코드를 작성해줘" -P my-api

# Multi-AI 토론 및 합의 (Debate) 실행 (Claude vs Antigravity)
python run.py debate --topic "REST vs GraphQL for Mobile Backend" --proposer claude --challenger agy
```

---

## 💡 핵심 아키텍처 요약

- **공용 칠판 (`blackboard/`)**: AI 프로세스 간 상태(`state.json`), 태스크(`tasks/`), 교환 산출물(`artifacts/`), 로그(`logs/`)를 공유하는 팀 협업 전용 공간.
- **프로젝트 격리 작업 공간 (`projects/<프로젝트명>/`)**: AI 팀이 실제 소스 코드, 패키지, 테스트 파일 등을 생성·수정하는 프로젝트별 독립 공간.
- **CLI 중심 자율 협업**: 별도의 워크플로우 YAML 파일 작성 없이, 터미널에서 자연어 명령을 입력받아 Conductor(Leader)가 기획하고 Worker들이 분담 구현.
- **실행 명령 및 실패 원인 투명 표시**: 실제 실행되는 AI CLI 명령어를 축약 없이 화면에 출력하며, 작업 실패 시 상세 에러 원인(`stderr`/`stdout`)을 즉시 표시.
- **다양한 협업 토폴로지**: 지휘자-워커(Conductor), 토론 및 합의(Debate), 파이프라인(Pipeline).
- **안전 감시자 & Git 격리**: Git Worktree 기반 변경 분리, 스냅샷 롤백, 무응답/무한 루프 방지.

---

## 📚 상세 문서 (Documentation)

자세한 설정 방법 및 아키텍처는 `docs/` 디렉터리에서 확인하실 수 있습니다:

- 📖 **[설정 및 실전 사용 매뉴얼 (Configuration & Setup Guide)](docs/configuration_guide.md)**  
  설치 후 실제 AI CLI(Claude, AGY, Aider) 연결, `.env` 환경 변수 설정, 팀 구성 및 트러블슈팅 단계별 가이드
- 🤖 **[Claude Code 연동 및 퀵스타트 가이드 (Claude Code Guide)](docs/claude_guide.md)**  
  Anthropic 공식 퀵스타트 기반 설치, 인증, 권한 모드(`auto`), 모델/노력 설정, `CLAUDE.md` 및 ModueHarness 연동 가이드
- 🚀 **[Google Antigravity 연동 가이드 (Antigravity Guide)](docs/antigravity_guide.md)**  
  Google Deepmind 공식 가이드 기반 `agy` CLI 설치, 인증, 모델(`gemini-3.8-flash-high` 등), 권한 자동화 및 하이브리드 팀 구성
- 🏛️ **[시스템 아키텍처 및 상세 기능 (Architecture & Features)](docs/architecture.md)**  
  전체 아키텍처 다이어그램, 3대 협업 토폴로지, 어댑터 계층, 블랙보드, 안전 감시자 및 로드맵
- 📝 **[명세 파일 작성 가이드 (Specifications Guide)](docs/specifications.md)**  
  AI 팀 명세(`agents.yaml`)와 작업 명세(`workflow.yaml`)의 분리 구성, Claude/Antigravity 혼합 구성 및 템플릿 변수 활용법
- 🛠️ **[CLI 명령어 레퍼런스 (CLI Reference)](docs/cli_reference.md)**  
  대화형 REPL(`/model`, `/effort`, `/jobs`, `/cmd`), `init`, `status`, `run`, `debate` 명령어 및 전체 옵션 가이드


---

## 📄 라이선스 (License)

[Apache License 2.0](LICENSE)
