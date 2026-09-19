# ModueHarness CLI 명령어 레퍼런스 (CLI Reference)

ModueHarness CLI 도구의 전체 실행 방식, 명령어 및 옵션 가이드입니다.

---

## 🎯 핵심 실행 구조 (Architecture)

ModueHarness는 **AI 간의 정보 교환**과 **실제 프로젝트 코드 구현**을 명확히 분리하여 작업합니다:

- **공용 칠판 (`blackboard/`)**: AI 에이전트 간 세션 상태(`state.json`), 태스크(`tasks/`), 교환 산출물(`artifacts/`, 예: `plan.md`, `synthesis_report.md`), 실행 로그(`logs/`) 전용 공간.
- **프로젝트 작업 공간 (`projects/<프로젝트명>/`)**: AI 에이전트들이 실제 소스 코드, 패키지 파일, 테스트 등을 직접 생성하고 수정하는 프로젝트별 격리 작업 폴더.

---

> 💡 **실행 명령어 표기 안내**:  
> 본 문서의 모든 명령어는 아래 3가지 방식으로 동일하게 실행할 수 있습니다:  
> - **방법 1 (루트 실행 파일, 가장 간편)**: `python run.py [명령어/옵션]` (환경변수 불필요)  
> - **방법 2 (전용 CLI 명령어)**: `modue-harness [명령어/옵션]` (`pip install -e .` 설치 후)  
> - **방법 3 (파이썬 모듈)**: `python -m modue_harness.cli [명령어/옵션]` (Windows는 `$env:PYTHONPATH="src"` 필요)

---

## 1. 대화형 CLI 모드 (Interactive REPL)

워크플로우 YAML 설정 파일 없이 터미널에서 대화형으로 AI 팀에게 자연어 명령을 내릴 수 있습니다.

```bash
# 기본 대화형 모드 시작
python run.py -i
# (또는: modue-harness -i)

# 특정 프로젝트를 지정하여 시작
python run.py -i -P my-web-app
# (또는: modue-harness -i -P my-web-app)
```

### 대화형 세션 내 특수 명령어
- `/project <이름>` (또는 `/p <이름>`): 활성 프로젝트 전환 (해당 폴더 자동 생성)
- `/projects`: 기존 생성된 프로젝트 목록 조회
- `/files` (또는 `/ls`): 현재 프로젝트 내 생성/수정된 파일 목록 조회
- `/status`: 공용 칠판 및 활성 프로젝트 상태 조회
- `/help`: 사용 가능한 명령어 안내
- `exit` / `quit` / `q`: 세션 종료

---

## 2. 단일 명령 직접 실행 (Direct Command)

CLI 명령줄에서 작업을 한 줄로 즉시 전달하여 실행합니다.

```bash
# 기본 프로젝트(default)에 작업 실행
python run.py "간단한 사칙연산 계산기 모듈과 테스트 코드를 작성해줘"

# 특정 프로젝트(projects/calculator/)를 지정하여 실행
python run.py "간단한 사칙연산 계산기 모듈과 테스트 코드를 작성해줘" -P calculator

# -p 플래그 사용 예시
python run.py -p "FastAPI 기반 회원가입 API 구현" -P user-service
```

### 공통 옵션
- `-p`, `--prompt`: 실행할 작업 지시사항 (문자열)
- `-P`, `--project`: 대상 프로젝트 폴더명 (기본값: `default` -> `projects/default/`)
- `--projects-dir`: 프로젝트 루트 디렉터리 경로 (기본값: `projects`)
- `--dir`, `-d`: 공용 칠판 디렉터리 경로 (기본값: `blackboard`)
- `--agents`, `-a`: 사용할 AI 팀 명세 파일 (`config/agents.yaml` 미존재 시 시스템 CLI 도구 자동 감지)
- `--agent`: 특정 단일 AI 에이전트 어댑터 지정 (예: `claude`, `agy`, `aider`, `generic`)

---

## 3. 프로젝트 목록 조회 (`projects`)

생성된 프로젝트 폴더 목록을 확인합니다.

```bash
python3 -m modue_harness.cli projects [--projects-dir <path>]
```

---

## 4. 환경 초기화 (`init`)

공용 칠판(`blackboard/`)과 프로젝트 디렉터리(`projects/`)를 초기화합니다.

```bash
python3 -m modue_harness.cli init [--dir <blackboard_path>] [--projects-dir <projects_path>]
```

---

## 5. 상태 조회 (`status`)

현재 공용 칠판의 세션 상태, 등록된 프로젝트, 태스크 큐 및 산출물을 출력합니다.

```bash
python3 -m modue_harness.cli status [--dir <blackboard_path>] [--projects-dir <projects_path>]
```

---

## 6. 워크플로우 명세 파일 실행 (`run`, 레거시 지원)

정적 워크플로우 YAML/JSON 명세 파일을 기반으로 파이프라인을 실행합니다.

```bash
python3 -m modue_harness.cli run --config <workflow.yaml> [OPTIONS]
```

### 옵션
- `--config`, `-c` *(필수)*: 실행할 워크플로우 명세 파일 경로
- `--agents`, `-a`: AI 팀 명세 파일 경로
- `--dir`, `-d`: 블랙보드 폴더 경로
- `--report`, `-r`: 마크다운 실행 결과 보고서 저장 경로 (예: `report.md`)

---

## 7. Multi-AI 토론 및 합의 (`debate`)

둘 이상의 AI CLI 간의 토론 및 판정관 합의 워크플로우를 즉시 실행합니다.

```bash
python3 -m modue_harness.cli debate --topic "Microservices vs Modular Monolith" [OPTIONS]
```
