# ModueHarness (모두의 하네스)

[![Version](https://img.shields.io/badge/version-0.4.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-43%20passed-brightgreen.svg)](tests/)

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
```

### 3. 워크플로우 실행 예시
```bash
# 다중 AI 협업 파이프라인 실행
PYTHONPATH=src python3 -m modue_harness.cli run --config examples/feature_workflow.yaml

# Multi-AI 토론 및 합의 (Debate) 실행
PYTHONPATH=src python3 -m modue_harness.cli debate --topic "REST vs GraphQL for Mobile Backend"
```

---

## 💡 핵심 아키텍처 요약

- **공용 칠판 (`blackboard/`)**: AI CLI 프로세스들이 투명하게 상태(`state.json`), 태스크(`tasks/`), 산출물(`artifacts/`), 로그(`logs/`)를 교환하는 프로젝트 내 가시 공간.
- **다양한 협업 토폴로지**:
  - **파이프라인 (Pipeline)**: 산출물 연쇄 전달 및 조건부/재시도 릴레이
  - **지휘자-워커 (Conductor)**: Leader AI의 동적 태스크 분해 및 종합
  - **토론 및 합의 (Debate)**: 다자 교차 토론 및 판정관 최종 합의안 도출
- **안전 감시자 & Git 격리**: Git Worktree 기반 변경 분리, 스냅샷 롤백, 무응답/무한 루프 방지.

---

## 📚 상세 문서 (Documentation)

자세한 설정 방법 및 아키텍처는 `docs/` 디렉터리에서 확인하실 수 있습니다:

- 📖 **[설정 및 실전 사용 매뉴얼 (Configuration & Setup Guide)](docs/configuration_guide.md)**  
  설치 후 실제 AI CLI(Claude, AGY, Aider) 연결, `.env` 환경 변수 설정, 팀 구성 및 트러블슈팅 단계별 가이드
- 🏛️ **[시스템 아키텍처 및 상세 기능 (Architecture & Features)](docs/architecture.md)**  
  전체 아키텍처 다이어그램, 3대 협업 토폴로지, 어댑터 계층, 블랙보드, 안전 감시자 및 로드맵
- 📝 **[명세 파일 작성 가이드 (Specifications Guide)](docs/specifications.md)**  
  AI 팀 명세(`agents.yaml`)와 작업 명세(`workflow.yaml`)의 분리 구성 및 템플릿 변수 활용법
- 🛠️ **[CLI 명령어 레퍼런스 (CLI Reference)](docs/cli_reference.md)**  
  `init`, `status`, `run`, `debate` 명령어 및 전체 옵션 가이드

---

## 📄 라이선스 (License)

[Apache License 2.0](LICENSE)
