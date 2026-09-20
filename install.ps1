# ModueHarness (모두의 하네스) - Windows PowerShell Installer & Updater
# Repository: https://github.com/jaenimi-dev/ModueHarness

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/jaenimi-dev/ModueHarness.git"
$RepoName = "ModueHarness"
$GhRepo = "jaenimi-dev/ModueHarness"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "🚀 ModueHarness 설치 및 전체 패키지 환경 구성" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Python 감지 및 버전 체크
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3"
} else {
    Write-Error "❌ 오류: Python이 시스템에 설치되어 있지 않습니다. Python 3.9 이상을 설치해 주세요."
    exit 1
}

Write-Host "✓ Python 감지됨: $pythonCmd" -ForegroundColor Green

# 2. 저장소 가져오기 또는 최신화 (Git / gh)
if ((Test-Path ".git") -and (git remote -v 2>$null | Select-String "ModueHarness")) {
    Write-Host "✓ 현재 ModueHarness 저장소 내부입니다. 최신 코드를 pull 합니다..." -ForegroundColor Yellow
    git pull origin main
} elseif (Test-Path "$RepoName\.git") {
    Write-Host "✓ 기존 '$RepoName' 디렉터리가 발견되었습니다. 해당 디렉터리로 이동 후 pull 합니다..." -ForegroundColor Yellow
    Set-Location $RepoName
    git pull origin main
} else {
    Write-Host "📦 ModueHarness 저장소를 내려받습니다..." -ForegroundColor Yellow
    if ((Get-Command gh -ErrorAction SilentlyContinue) -and (gh auth status 2>$null)) {
        Write-Host "✓ GitHub CLI(gh)를 사용하여 저장소를 클론합니다..." -ForegroundColor Green
        gh repo clone $GhRepo $RepoName
    } elseif (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Host "✓ Git을 사용하여 저장소를 클론합니다..." -ForegroundColor Green
        git clone $RepoUrl $RepoName
    } else {
        Write-Error "❌ 오류: git 또는 gh 명령어가 설치되어 있지 않습니다."
        exit 1
    }
    Set-Location $RepoName
}

# 3. 전체 패키지 한 번에 설치 (Core + Dev + Web UI NiceGUI + Terminal TUI Textual)
Write-Host ""
Write-Host "⚙️ 전체 패키지(Core, Dev, NiceGUI Web UI, Textual TUI) 한 번에 설치 중..." -ForegroundColor Cyan
& $pythonCmd -m pip install --upgrade pip
& $pythonCmd -m pip install -e ".[all]"

# 4. 설치 검증 (테스트 실행)
Write-Host ""
Write-Host "🧪 설치 검증 테스트를 실행합니다..." -ForegroundColor Cyan
& $pythonCmd -m pytest -q
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 모든 단위 테스트 통과 완료!" -ForegroundColor Green
} else {
    Write-Host "⚠️ 일부 테스트 경고가 발생했으나 설치는 완료되었습니다." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "🎉 ModueHarness 설치 및 구성이 완료되었습니다!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "💡 바로 시작하는 방법:" -ForegroundColor White
Write-Host "   Set-Location $(Get-Location)"
Write-Host "   $pythonCmd run.py -i                     # 대화형 REPL 모드 실행"
Write-Host "   $pythonCmd run.py --ui                   # 웹 UI 대시보드 (http://127.0.0.1:8080)"
Write-Host "   $pythonCmd run.py --tui                  # 터미널 TUI 대시보드"
Write-Host "==================================================" -ForegroundColor Cyan
