# ModueHarness 설치 및 환경 구성 가이드 (Installation Guide)

이 문서는 **ModueHarness(모두의 하네스)**를 사용자의 운영체제(Linux, macOS, Windows)에 설치하고 실행 환경을 구성하는 상세 가이드입니다.

---

## 📋 시스템 요구사항 (Prerequisites)

* **Python**: `3.9` 이상 (`python3 --version` 또는 `python --version`)
* **Git 도구**: `git` 또는 GitHub CLI(`gh`)
* **운영체제**: Linux (Ubuntu, Debian, Fedora, RHEL 등), macOS, Windows (PowerShell)
* **AI CLI 도구 (선택 사항)**: 사용하고자 하는 AI 도구 중 최소 하나 이상
  - [Claude Code](claude_guide.md) (`claude`)
  - [Google Antigravity](antigravity_guide.md) (`agy`)
  - [OpenAI ChatGPT Codex](codex_guide.md) (`codex`)
  - [Aider](configuration_guide.md#3-aider-aider) (`aider`)
  - 또는 로컬 LLM / Python 커스텀 스크립트 (`generic`)

---

## 🚀 1. 원클릭 자동 설치 (권장)

공개 저장소로부터 최신 소스코드를 내려받고, 의존성 패키지를 일괄 설치하며, 단위 테스트 검증까지 자동으로 진행합니다.

### 🐧 Linux / 🍎 macOS
```bash
curl -fsSL https://raw.githubusercontent.com/jaenimi-dev/ModueHarness/main/install.sh | bash
```

### 🪟 Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/jaenimi-dev/ModueHarness/main/install.ps1 | iex
```

> 💡 **자동 설치 스크립트의 동작 내용**:
> 1. 시스템의 Python 3.9+ 버전 확인
> 2. `gh`(GitHub CLI) 또는 `git`을 감지하여 `ModueHarness` 저장소를 클론 (이미 저장소 폴더 내부인 경우 `git pull`로 최신화)
> 3. `pip install -e ".[all]"` 명령으로 코어 프레임워크 및 Web UI/TUI 패키지 일괄 설치
> 4. `pytest`를 통한 101개 단위 테스트 실행 및 설치 검증

---

## 🛠️ 2. 수동 설치 (Manual Installation)

Git 또는 GitHub CLI(`gh`)로 저장소를 직접 클론하고 패키지를 설치하는 방법입니다.

### 1단계: 저장소 내려받기
```bash
# 방법 A: 표준 Git 사용
git clone https://github.com/jaenimi-dev/ModueHarness.git

# 방법 B: GitHub CLI (gh) 사용
gh repo clone jaenimi-dev/ModueHarness

cd ModueHarness
```

### 2단계: 패키지 설치
원하는 환경에 맞춰 옵션을 선택하여 설치합니다.

```bash
# [추천] 전체 패키지 한 번에 설치 (Core + Dev + Web UI NiceGUI + Terminal TUI Textual)
pip install -e ".[all]"

# (선택) CLI 코어와 단위 테스트 도구만 가볍게 설치할 때
pip install -e ".[dev]"

# (선택) Web UI 및 TUI 대시보드 도구만 추가 설치할 때
pip install -e ".[ui]"
```

---

## 🔄 3. 최신 버전 업데이트 (Update)

이미 저장소를 클론받은 상태에서 최신 기능과 패치를 적용하려면:

```bash
cd ModueHarness

# 최신 커밋 가져오기
git pull origin main

# 변경된 의존성 패키지 갱신
pip install -e ".[all]"
```
*(또는 저장소 폴더 내에서 `./install.sh` 실행)*

---

## 🧪 4. 설치 검증 (Verification)

설치가 성공적으로 완료되었는지 단위 테스트와 CLI 버전을 확인합니다.

```bash
# 단위 테스트 실행 (101개 테스트 통과 확인)
python3 -m pytest -q

# 버전 확인
python run.py --version
# (또는: modue-harness --version)
```

---

## 🚀 5. 기본 실행 (Getting Started)

설치 완료 후 아래 방법 중 원하는 모드를 선택하여 실행합니다:

```bash
# 1) [추천] 대화형 CLI 모드 (REPL) 실행
python run.py -i -P my-web-app
# (또는 pip 설치 후: modue-harness -i -P my-web-app)

# 2) 🌐 Web UI 대시보드 (NiceGUI 브라우저 화면: http://127.0.0.1:8080)
python run.py --ui -P my-web-app

# 3) 💻 Terminal TUI 대시보드 (Textual 터미널 콘솔 화면)
python run.py --tui -P my-web-app

# 4) 단일 자연어 명령 직접 실행
python run.py "FastAPI 기반 REST API와 테스트 코드를 작성해줘" -P my-api
```

---

## ⚠️ 6. 트러블슈팅 (Troubleshooting)

### Q1. UI 실행 시 `NiceGUI is not installed` 또는 `Textual is not installed` 오류가 발생합니다.
* **원인**: 패키지 설치 시 `[ui]` 또는 `[all]` 옵션을 제외하고 설치한 경우 발생합니다.
* **해결 방법**:
  ```bash
  pip install "modue-harness[ui]"
  # 또는 개별 설치: pip install nicegui textual
  ```

### Q2. Windows에서 `codex` 또는 `claude` 설치 후 인식이 안 됩니다.
* **원인**: 설치 스크립트가 윈도우 환경변수(PATH)에 실행 경로를 추가했으나, 기존 터미널 창에 반영되지 않은 상태입니다.
* **해결 방법**:
  현재 열려 있는 모든 PowerShell 창과 VS Code 터미널을 닫고 **새로운 PowerShell 창을 열어 재기동**합니다.

---

## 📚 다음 단계 (Next Steps)

설치를 마쳤다면 다음 가이드를 참고하여 AI 팀 설정 및 고급 기능을 활용해 보세요:

* **[CLI 명령어 레퍼런스 및 실전 옵션](cli_reference.md)**
* **[AI CLI 설정 및 실전 매뉴얼](configuration_guide.md)**
* **[Claude Code 연동 가이드](claude_guide.md)**
* **[Google Antigravity 연동 가이드](antigravity_guide.md)**
* **[OpenAI ChatGPT Codex 연동 가이드](codex_guide.md)**
