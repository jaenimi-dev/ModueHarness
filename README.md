# ModueHarness (모두의 하네스)

[![Version](https://img.shields.io/badge/version-0.8.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-106%20passed-brightgreen.svg)](tests/)

**ModueHarness**는 Claude Code, Google Antigravity(AGY), OpenAI ChatGPT Codex 등 다양한 AI CLI 도구들을 하나의 유기적인 팀으로 엮어 소프트웨어 엔지니어링 작업을 자율적·협업적으로 해결하는 Multi-AI CLI 하네스(Harness) 프레임워크입니다.

---

## 💡 핵심 아키텍처 요약

- **프로젝트별 격리 칠판 (`blackboard/<프로젝트명>/`)**: AI 프로세스 간 상태(`state.json`), 태스크(`tasks/`), 교환 산출물(`artifacts/`), 작업 이력(`jobs/`), 로그(`logs/`)를 프로젝트별로 안전하게 공유하는 협업 전용 공간.
- **프로젝트 격리 작업 공간 (`projects/<프로젝트명>/`)**: AI 팀이 실제 소스 코드, 패키지, 테스트 파일 등을 생성·수정하는 프로젝트별 독립 공간.
- **CLI 중심 자율 협업**: 별도의 워크플로우 YAML 파일 작성 없이, 터미널에서 자연어 명령을 입력받아 Conductor(Leader)가 기획하고 Worker들이 분담 구현.
- **실행 명령 및 실패 원인 투명 표시**: 실제 실행되는 AI CLI 명령어를 축약 없이 화면에 출력하며, 작업 실패 시 상세 에러 원인(`stderr`/`stdout`)을 즉시 표시.
- **다양한 협업 토폴로지**: 지휘자-워커(Conductor), 토론 및 합의(Debate), 파이프라인(Pipeline).
- **안전 감시자 & Git 격리**: Git Worktree 기반 변경 분리, 스냅샷 롤백, 무응답/무한 루프 방지.

---

## 🚀 빠른 시작 (Quick Start)

> 📦 **상세 설치 및 환경 구성 매뉴얼**: **[docs/installation.md](docs/installation.md)**  
> 🛠️ **CLI 명령어 레퍼런스 및 실전 옵션**: **[docs/cli_reference.md](docs/cli_reference.md)**

터미널에서 아래 원라인 명령어를 실행하면 저장소 복제부터 전체 패키지 설치(`pip install -e ".[all]"`) 및 검증까지 자동으로 완료됩니다:

- **Linux / macOS**:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/jaenimi-dev/ModueHarness/main/install.sh | bash
  ```
- **Windows (PowerShell)**:
  ```powershell
  irm https://raw.githubusercontent.com/jaenimi-dev/ModueHarness/main/install.ps1 | iex
  ```

설치 후 즉시 원하는 모드로 시작할 수 있습니다:
```bash
python run.py -i -P my-project    # [추천] 대화형 CLI 모드 (REPL)
python run.py --ui -P my-project  # 🌐 Web UI 대시보드 (브라우저 화면)
```

*(수동 설치, 세부 패키지 옵션(`[dev]`, `[ui]`), 단위 테스트 검증 및 트러블슈팅은 **[설치 가이드(docs/installation.md)](docs/installation.md)**를, 전체 CLI 명령어와 옵션 예시는 **[CLI 레퍼런스(docs/cli_reference.md)](docs/cli_reference.md)**를 참조하세요.)*

---

## 📚 상세 문서 (Documentation)

ModueHarness의 상세 설정 방법, 지원 AI CLI 연동 가이드(Claude, AGY, Codex), 시스템 아키텍처 및 CLI 명령어 레퍼런스는 **[docs 디렉터리 문서 인덱스 (docs/README.md)](docs/README.md)**에서 체계적으로 확인하실 수 있습니다.

👉 **[전체 문서 인덱스 둘러보기 (docs/README.md)](docs/README.md)**

---

## 🔮 향후 발전 방향 (Future Roadmap)

ModueHarness의 3대 핵심 발전 축(어댑터 생태계 확장, 원격지 분산 노드 연결, 엔터프라이즈 보안 분석 및 가드레일)과 세부 추진 과제는 **[FUTURE.md](FUTURE.md)**에서 확인하실 수 있습니다.

---

## 📄 라이선스 (License)

[Apache License 2.0](LICENSE)
