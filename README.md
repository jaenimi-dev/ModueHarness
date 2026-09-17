# ModueHarness (모두의 하네스)

> **Current Version:** `0.3.0`

**ModueHarness**는 다양한 AI CLI 도구(예: `claude`, `agy`, `aider`, `copilot` 등)를 하나의 유기적인 팀으로 오케스트레이션하여 소프트웨어 엔지니어링 작업을 자율적·협업적으로 해결하는 Multi-AI CLI 하네스 프레임워크입니다.

---

## 🌟 핵심 특징

- **CLI 어댑터 계층 (`adapters`)**: Claude Code(`claude`), Antigravity CLI(`agy`), Aider(`aider`) 및 범용 쉘 커맨드를 통일된 인터페이스(`BaseCLIAdapter`)로 실행하고 입출력 스트림/ANSI 코드를 정규화합니다.
- **공용 칠판 (`blackboard/`)**: 서로 다른 프로세스로 동작하는 AI CLI들이 작업 상태(`state.json`), 세부 태스크 큐(`tasks/`), 산출물(`artifacts/`), 실행 로그(`logs/`)를 가시적인 프로젝트 폴더를 통해 투명하게 공유합니다.
- **선언적 파이프라인 엔진 (`engine`)**: YAML 또는 JSON 설정을 통해 팀 구성, 역할, 순차적 릴레이 및 산출물 전달을 간결하게 정의하고 실행합니다.

---

## 📁 디렉터리 구조

```
.
├── blackboard/                 # AI 협업 공용 칠판 (실행 시 생성/관리)
│   ├── state.json              # 워크플로우 실행 상태 및 세션 정보
│   ├── tasks/                  # 단계별 하위 태스크 명세 및 결과
│   ├── artifacts/              # AI 간 주고받는 산출물 (기획서, 코드 패치 등)
│   └── logs/                   # AI CLI 원시 실행 로그 (git ignore 처리)
├── src/
│   └── modue_harness/
│       ├── __init__.py         # 패키지 진입점 (v0.1.0)
│       ├── cli.py              # CLI 인터페이스 (init, status, run 등)
│       ├── py.typed            # PEP 561 타입 마커
│       ├── core/               # 핵심 기반 시스템
│       │   ├── types.py        # Task, TaskStatus, TurnContext, TurnResult
│       │   ├── blackboard.py   # Blackboard 공유 칠판 관리자
│       │   ├── config.py       # 기본 설정 모델
│       │   └── harness.py      # BaseHarness 추상 기본 클래스
│       ├── adapters/           # AI CLI 어댑터 모듈
│       │   ├── base.py         # BaseCLIAdapter (서브프로세스, ANSI 제거, 타임아웃)
│       │   ├── generic.py      # 범용 CLI 어댑터
│       │   ├── claude.py       # Claude Code CLI 어댑터
│       │   ├── agy.py          # Antigravity (AGY) CLI 어댑터
│       │   └── aider.py        # Aider CLI 어댑터
│       └── engine/             # 워크플로우 오케스트레이션 엔진
│           ├── workflow.py     # YAML/JSON 워크플로우 로더 및 모델
│           └── pipeline.py     # 순차적 릴레이 파이프라인 러너
├── tests/                      # 포괄적인 단위/통합 테스트 (23개 테스트 통과)
├── CHANGELOG.md                # 시맨틱 버저닝 변경 이력
├── LICENSE                     # Apache 2.0 라이선스
├── pyproject.toml              # 프로젝트 빌드 및 의존성 설정
└── setup.py                    # 호환용 패키징 설정
```

---

## 🚀 빠른 시작

### 1. 개발 환경 설정
```bash
pip install -e ".[dev]"
```

### 2. 테스트 실행
```bash
python3 -m pytest -v
```

### 3. CLI 사용법

#### 블랙보드 초기화
```bash
PYTHONPATH=src python3 -m modue_harness.cli init
```

#### 현재 상태 및 태스크 확인
```bash
PYTHONPATH=src python3 -m modue_harness.cli status
```

#### 워크플로우 실행
```bash
PYTHONPATH=src python3 -m modue_harness.cli run --config examples/simple_pipeline.yaml
```

---

## 📝 워크플로우 예시 (`workflow.yaml`)

```yaml
name: "feature-collaboration"
workflow:
  topology: "pipeline"
  timeout_per_step: 300
  steps:
    - id: "step_spec"
      agent: "planner"
      instruction: "기능 명세 및 아키텍처 초안을 작성하라."
      output_artifact: "spec.md"

    - id: "step_code"
      agent: "coder"
      input_artifacts: ["spec.md"]
      instruction: "spec.md 명세에 맞춰 코드를 구현하고 테스트하라."

agents:
  planner:
    adapter: "claude"
    command: "claude"
    role: "Architect & Planner"

  coder:
    adapter: "agy"
    command: "agy"
    role: "Implementation Engineer"
```
