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

### 대화형 실행 방식
1. **포그라운드 실시간 실행 (기본)**: 명령을 입력하면 기획(1단계) -> 구현(2단계) -> 종합(3단계)의 진행 상황이 실시간으로 터미널에 출력됩니다. (`Ctrl+C`로 즉시 취소 가능)
2. **백그라운드 비동기 실행 (`&` 또는 `/bg`)**: 명령 끝에 `&`를 붙이거나 `/bg <명령어>`로 실행하면, 프롬프트가 즉시 반환되어 작업을 백그라운드에서 수행하면서 다른 명령을 계속 입력할 수 있습니다.

### 대화형 세션 내 특수 명령어
- `자연어 명령 &` (또는 `/bg <명령어>`): 백그라운드 비동기 작업 실행 (프롬프트 즉시 반환)
- `/model [에이전트명] [모델명]`: AI 모델 확인 및 실시간 변경 (예: `/model sonnet`, `/model agy gemini-3.8-flash-high`)
- `/effort [에이전트명] [수준]`: AI 추론 노력(Reasoning Effort/Thinking) 설정
  - Claude: `low`, `medium`, `high`, `max`, `off`
  - Antigravity: `low`, `medium`, `high`
- `/timeout [초|off]`: AI 실행 타임아웃 설정 또는 해제 (기본값: 해제됨 / 무제한 대기)
  - `/timeout 600` (600초 설정), `/timeout off` (무제한 해제)
- `/cmd` (또는 `/last-cmd`): 최근 실행된 실제 AI CLI 명령어 전체 확인
- `/jobs`: 백그라운드 작업 목록, 현재 진행 단계(Stage), 실패 시 상세 사유 조회
- `/cancel [job_id]` (또는 `/stop`): 실행 중인 작업 즉시 취소 및 중단
- `/project <이름>` (또는 `/p <이름>`): 활성 프로젝트 전환 (해당 폴더 자동 생성)
- `/projects`: 기존 생성된 프로젝트 목록 조회
- `/files` (또는 `/ls`): 현재 프로젝트 내 생성/수정된 파일 목록 조회
- `/status`: 공용 칠판, 활성 프로젝트, 세션 타임아웃 및 백그라운드 작업 상태 조회
- `/help`: 사용 가능한 명령어 안내
- `exit` / `quit` / `q`: 세션 종료

### 작업 실패 시 원인 안내
작업(기획, 서브태스크 구현, 종합 보고서 작성 등)이 실패로 종료되는 경우 원인을 즉시 파악할 수 있도록 상세 오류가 표시됩니다:
- **실시간 진행 스트리밍**: 실패한 단계에서 `❌ 서브태스크 실패 원인: ...` 즉시 출력
- **최종 요약 리포트**: `❌ [실패 상세 원인]: ...` 및 서브태스크 목록에 `❌ 오류 상세: ...` 명시
- **백그라운드 작업 (`/jobs`)**: 실패한 작업 목록에 `❌ 실패 사유: ...` 출력
- **표준 에러(stderr) 자동 추출**: CLI 프로세스가 비정상 종료(non-zero exit code)될 때 프로세스의 stderr/stdout 에러 메시지를 최대 5줄까지 추출하여 원인을 명확하게 전달합니다.

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

# Antigravity CLI로 모델 및 추론 노력 지정 실행
python run.py "REST API 엔드포인트 구현" -P my-api --agent agy -m gemini-3.8-flash-high -e high

# Claude Code로 Sonnet 모델 및 최대 추론 노력 지정 실행
python run.py "알고리즘 최적화" -P algo --agent claude -m sonnet -e high

# 필요 시 타임아웃(예: 600초)을 지정하여 실행 (기본값은 무제한)
python run.py "대규모 리팩토링" -P refactor -t 600
```

### 공통 옵션
- `-p`, `--prompt`: 실행할 작업 지시사항 (문자열)
- `-P`, `--project`: 대상 프로젝트 폴더명 (기본값: `default` -> `projects/default/`)
- `--projects-dir`: 프로젝트 루트 디렉터리 경로 (기본값: `projects`)
- `--dir`, `-d`: 공용 칠판 디렉터리 경로 (기본값: `blackboard`)
- `--agents`, `-a`: 사용할 AI 팀 명세 파일 (`config/agents.yaml` 미존재 시 시스템 CLI 도구 자동 감지)
- `--agent`: 특정 단일 AI 에이전트 어댑터 지정 (예: `claude`, `agy` 또는 `antigravity`, `aider`, `generic`)
- `-m`, `--model`: 사용할 AI 모델명 지정 (Claude: `sonnet`, `opus`, `haiku` 등 / Antigravity: `gemini-3.8-flash-high`, `gemini-3.5-pro` 등)
- `-e`, `--effort`: AI 추론 노력(Reasoning Effort) 수준 지정 (Claude: `low`, `medium`, `high`, `max` / Antigravity: `low`, `medium`, `high`)
- `-t`, `--timeout`: AI 실행 1턴당 타임아웃(초) 지정 (기본값: `None` / 무제한 대기)

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
