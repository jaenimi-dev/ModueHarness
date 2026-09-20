#!/usr/bin/env bash
# ModueHarness (모두의 하네스) - One-Line Installer & Updater
# Repository: https://github.com/jaenimi-dev/ModueHarness

set -e

REPO_URL="https://github.com/jaenimi-dev/ModueHarness.git"
REPO_NAME="ModueHarness"
GH_REPO="jaenimi-dev/ModueHarness"

echo "=================================================="
echo "🚀 ModueHarness 설치 및 전체 패키지 환경 구성"
echo "=================================================="

# 1. Python 감지 및 버전 체크
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ 오류: Python 3이 시스템에 설치되어 있지 않습니다."
    echo "   Python 3.9 이상을 설치한 후 다시 실행해주세요."
    exit 1
fi

PY_VER=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python 감지됨: $PYTHON_CMD ($PY_VER)"

# 2. 저장소 가져오기 또는 최신화 (Git / gh)
if [ -d ".git" ] && git remote -v 2>/dev/null | grep -qi "ModueHarness"; then
    echo "✓ 현재 ModueHarness 저장소 내부입니다. 최신 코드를 pull 합니다..."
    git pull origin main || git pull
elif [ -d "$REPO_NAME/.git" ]; then
    echo "✓ 기존 '$REPO_NAME' 디렉터리가 발견되었습니다. 해당 디렉터리로 이동 후 pull 합니다..."
    cd "$REPO_NAME"
    git pull origin main || git pull
else
    echo "📦 ModueHarness 저장소를 내려받습니다..."
    if command -v gh &>/dev/null && gh auth status &>/dev/null; then
        echo "✓ GitHub CLI(gh)를 사용하여 저장소를 클론합니다..."
        gh repo clone "$GH_REPO" "$REPO_NAME"
    elif command -v git &>/dev/null; then
        echo "✓ Git을 사용하여 저장소를 클론합니다..."
        git clone "$REPO_URL" "$REPO_NAME"
    else
        echo "❌ 오류: git 또는 gh 명령어가 설치되어 있지 않습니다."
        exit 1
    fi
    cd "$REPO_NAME"
fi

# 3. 전체 패키지 한 번에 설치 (Core + Dev + Web UI NiceGUI + Terminal TUI Textual)
echo ""
echo "⚙️ 전체 패키지(Core, Dev, NiceGUI Web UI, Textual TUI) 한 번에 설치 중..."
$PYTHON_CMD -m pip install --upgrade pip
$PYTHON_CMD -m pip install -e ".[all]"

# 4. 설치 검증 (테스트 실행)
echo ""
echo "🧪 설치 검증 테스트를 실행합니다..."
if $PYTHON_CMD -m pytest -q; then
    echo "✓ 모든 단위 테스트 통과 완료!"
else
    echo "⚠️ 일부 테스트 경고가 발생했으나 설치는 완료되었습니다."
fi

echo ""
echo "=================================================="
echo "🎉 ModueHarness 설치 및 구성이 완료되었습니다!"
echo "=================================================="
echo "💡 바로 시작하는 방법:"
echo "   cd $(pwd)"
echo "   $PYTHON_CMD run.py -i                     # 대화형 REPL 모드 실행"
echo "   $PYTHON_CMD run.py --ui                   # 웹 UI 대시보드 (http://127.0.0.1:8080)"
echo "   $PYTHON_CMD run.py --tui                  # 터미널 TUI 대시보드"
echo "=================================================="
