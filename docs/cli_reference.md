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

# 기존 Git 또는 GitHub(gh) 저장소를 클론받아 작업할 때
# 1) git clone https://github.com/org/my-repo.git projects/my-repo
#    (또는 gh repo clone org/my-repo projects/my-repo)
# 2) 저장소 폴더명을 -P 인자로 전달하여 실행
python run.py "기존 코드베이스 분석 및 버그 수정" -P my-repo
```

### 공통 옵션
- `-p`, `--prompt`: 실행할 작업 지시사항 (문자열)
- `-P`, `--project`: 대상 프로젝트 폴더명 (기본값: `default` -> `projects/default/`). 외부 Git/GitHub 저장소는 `git clone` 또는 `gh repo clone`으로 `projects/<저장소명>`에 클론한 후 그 이름을 전달합니다.
- `--projects-dir`: 프로젝트 루트 디렉터리 경로 (기본값: `projects`)
- `--dir`, `-d`: 공용 칠판 디렉터리 경로 (기본값: `blackboard`)
- `--agents`, `-a`: 사용할 AI 팀 명세 파일 (`config/agents.yaml` 미존재 시 시스템 CLI 도구 자동 감지)
- `--agent`: 특정 단일 AI 에이전트 어댑터 지정 (예: `claude`, `agy` 또는 `antigravity`, `codex`, `aider`, `generic`)
- `-m`, `--model`: 사용할 AI 모델명 지정 (Claude: `sonnet`, `opus` 등 / Antigravity: `gemini-3.8-flash-high` 등 / Codex: `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`)
- `-e`, `--effort`: AI 추론 노력(Reasoning Effort) 수준 지정 (Claude: `low`, `medium`, `high`, `max` / Antigravity & Codex: `low`, `medium`, `high`)
- `-t`, `--timeout`: AI 실행 1턴당 타임아웃(초) 지정 (기본값: `None` / 무제한 대기)

---

## 3. 프로젝트 목록 조회 및 삭제 (`projects`)

생성된 프로젝트 폴더 목록을 확인하거나 특정 프로젝트를 삭제합니다.

```bash
# 생성된 프로젝트 목록 조회
python run.py projects
# (또는: modue-harness projects)

# 프로젝트 및 해당 격리 블랙보드 영구 삭제
python run.py projects --delete <프로젝트명>
# (또는: modue-harness projects --delete <프로젝트명>)
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
python run.py debate --topic "Microservices vs Modular Monolith" [OPTIONS]
# (또는: modue-harness debate --topic "Microservices vs Modular Monolith" [OPTIONS])
```

---

## 8. Web UI 대시보드 (`ui`, `--ui`)

웹 브라우저에서 3분할 콕핏 화면(명령어 디스패처, 실시간 AI 실행 로그 스트림, 칠판 산출물 및 소스 코드 뷰어)을 통해 AI 팀을 제어하고 모니터링합니다.

```bash
# 기본 Web UI 실행 (기본 포트: 8080, 브라우저 자동 오픈)
python run.py --ui
# (또는: modue-harness ui)

# 특정 프로젝트 및 호스트/포트 지정 실행
python run.py --ui -P my-web-app --host 0.0.0.0 --port 9000
# (또는: modue-harness ui -P my-web-app --host 0.0.0.0 --port 9000)

# 브라우저 자동 팝업 없이 서버만 백그라운드로 띄울 때
modue-harness ui --no-browser
```

### 의존성 설치 안내 및 트러블슈팅
Web UI는 **NiceGUI** 라이브러리를 사용하며, CLI 핵심 코어의 경량화를 위해 **선택적 의존성(Optional Dependency)**으로 분리되어 있습니다.

NiceGUI가 설치되지 않은 상태에서 `ui` 명령어를 실행하면 다음과 같은 친절한 가이드 메시지가 출력되고 종료됩니다:

```text
$ modue-harness ui
🌐 Starting ModueHarness Web UI at http://127.0.0.1:8080 ...
❌ NiceGUI is not installed. Please install it using: pip install 'modue-harness[ui]' or pip install nicegui
```

**해결 방법**:  
터미널에서 아래 명령어 중 하나를 실행하여 UI 의존성을 설치합니다:
```bash
# 권장: ModueHarness UI 패키지 일괄 설치 (NiceGUI + Textual)
pip install "modue-harness[ui]"
# 또는 개발 설치 시: pip install -e ".[ui]"

# 또는 NiceGUI만 단독 설치
pip install nicegui
```

### 옵션
- `-P`, `--project`: 초기 활성 프로젝트 이름 (기본값: `default`)
- `--host`: 웹 서버 바인딩 호스트 (기본값: `127.0.0.1`)
- `--port`: 웹 서버 포트 번호 (기본값: `8080`)
- `--no-browser`: 웹 브라우저 자동 열기 비활성화
- `--agents`, `-a`: AI 팀 명세 파일 경로
- `--dir`, `-d`: 블랙보드 폴더 경로
- `--projects-dir`: 프로젝트 베이스 디렉터리 경로

---

## 9. 터미널 TUI 대시보드 (`tui`, `--tui`)

SSH 원격 세션이나 순수 터미널 콘솔 환경에서 전체 화면(Full-screen) TUI 콕핏을 제공합니다.

```bash
# 기본 터미널 TUI 실행
python run.py --tui
# (또는: modue-harness tui)

# 특정 프로젝트를 지정하여 TUI 실행
python run.py --tui -P my-service
# (또는: modue-harness tui -P my-service)
```

### 의존성 설치 안내 및 트러블슈팅
TUI는 **Textual** 라이브러리를 사용하며, 미설치 시 다음과 같은 안내 메시지가 출력됩니다:

```text
$ modue-harness tui
❌ Textual is not installed. Please install it using: pip install 'modue-harness[ui]' or pip install textual
```

**해결 방법**:
```bash
# UI 패키지 일괄 설치
pip install "modue-harness[ui]"
# 또는 개발 설치 시: pip install -e ".[ui]"

# 또는 Textual만 단독 설치
pip install textual
```

### 단축키 안내
- `q`: TUI 종료
- `c`: 현재 실행 중인 AI 작업 즉시 취소
- `Tab` / `Shift+Tab`: 입력 필드 및 버튼 간 포커스 전환
