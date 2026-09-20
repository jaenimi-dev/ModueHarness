# ModueHarness 문서 인덱스 (Documentation Index)

ModueHarness의 전체 기능, 환경 설정, 지원 AI CLI 도구 연동 및 아키텍처에 대한 상세 문서 목록입니다.

---

## 🚀 시작하기 & 환경 구성

- 📦 **[설치 및 환경 구성 가이드 (installation.md)](installation.md)**  
  원클릭 자동 설치 스크립트(`install.sh`, `install.ps1`), Git/gh를 통한 수동 설치, 단계별 의존성 패키지 옵션(`[all]`, `[ui]`, `[dev]`) 및 트러블슈팅 가이드.
- 📖 **[설정 및 실전 사용 매뉴얼 (configuration_guide.md)](configuration_guide.md)**  
  설치 후 실제 AI CLI 연결, `.env` 환경 변수 설정, AI 팀 구성(`agents.yaml`), 워크플로우 정의(`workflow.yaml`) 및 실행 트러블슈팅 단계별 가이드.

---

## 🤖 AI CLI 연동 가이드

- 🤖 **[Claude Code 연동 및 퀵스타트 가이드 (claude_guide.md)](claude_guide.md)**  
  Anthropic 공식 퀵스타트 기반 `claude` CLI 설치, 인증, 권한 자동화 모드(`auto`), 모델 및 노력(Effort) 설정, `CLAUDE.md` 메모리 파일 및 ModueHarness 연동 가이드.
- 🚀 **[Google Antigravity 연동 가이드 (antigravity_guide.md)](antigravity_guide.md)**  
  Google Deepmind 공식 가이드 기반 `agy` CLI 설치, 인증, 모델(`gemini-3.8-flash-high`, `gemini-3.1-pro-high`), 무인 자동화 권한 플래그 및 하이브리드 팀 구성.
- 🧠 **[OpenAI ChatGPT Codex CLI 연동 가이드 (codex_guide.md)](codex_guide.md)**  
  OpenAI 공식 가이드 기반 `codex` CLI 설치, `codex login` 인증, 모델(`gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`), 샌드박스 작업 공간 쓰기 권한 설정 및 연동 가이드.

---

## 🏛️ 아키텍처 및 레퍼런스

- 🏛️ **[시스템 아키텍처 및 상세 기능 (architecture.md)](architecture.md)**  
  전체 시스템 아키텍처 다이어그램, 3대 협업 토폴로지(Conductor, Debate, Pipeline), 어댑터 계층, 프로젝트 격리 블랙보드, 안전 감시자(Supervisor) 및 기술 로드맵.
- 📝 **[명세 파일 작성 가이드 (specifications.md)](specifications.md)**  
  AI 팀 명세(`agents.yaml`)와 작업 명세(`workflow.yaml`)의 분리 구성, Claude/Antigravity/Codex 혼합 구성 및 템플릿 변수 활용법.
- 🛠️ **[CLI 명령어 레퍼런스 (cli_reference.md)](cli_reference.md)**  
  대화형 REPL 모드(`/model`, `/effort`, `/timeout`, `/cmd`, `/jobs`, `/cancel`), 프로젝트 관리(`projects --delete`), `init`, `status`, `run`, `debate` 명령어 및 전체 옵션 레퍼런스.
- 🔮 **[향후 발전 방향 및 로드맵 (FUTURE.md)](../FUTURE.md)**  
  더 많은 AI CLI 어댑터 확장, 원격지 분산 AI 노드 연결 및 엔터프라이즈 보안 향상 분석/가드레일 적용 로드맵.

