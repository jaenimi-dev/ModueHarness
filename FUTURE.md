# ModueHarness 향후 발전 방향 및 로드맵 (Future Roadmap)

ModueHarness(모두의 하네스)는 Claude Code, Google Antigravity(AGY), OpenAI Codex 등 다양한 AI CLI 도구와 OpenRouter 기반 내장 에이전트를 하나의 유기적인 엔지니어링 팀으로 엮는 오케스트레이션 프레임워크입니다.  
ModueHarness가 더욱 강력하고 안전하며 확장성 높은 엔터프라이즈급 멀티 AI 협업 플랫폼으로 도약하기 위한 **3대 핵심 발전 축(Strategic Pillars)**을 정의합니다.

---

## 🧭 3대 핵심 발전 축 (Three Strategic Pillars)

```
┌────────────────────────────────────────────────────────────────────────┐
│                   ModueHarness 미래 발전 핵심 축                        │
└────────────────────────────────────────────────────────────────────────┘
       │
       ├─ [Pillar 1] 🌐 더 많은 AI 지원을 위한 어댑터 생태계 확장
       │      • GitHub Copilot CLI, Cursor/Windsurf CLI 연동
       │      • OpenRouter 및 Ollama/vLLM 등 OpenAI 호환 API 내장 에이전트 고도화
       │      • 플러그인 기반 커스텀 어댑터 SDK 제공
       │
       ├─ [Pillar 2] 🌍 원격지 로그인 AI 연결 및 분산 협업 노드 확장
       │      • SSH / Remote Agent Bridge를 통한 이기종 서버 AI 연결
       │      • 원격 인증 세션/토큰 프록시 및 브릿지
       │      • 분산 블랙보드 동기화 (Distributed Blackboard Sync)
       │
       └─ [Pillar 3] 🛡️ 엔터프라이즈급 보안 향상 분석 및 안전 가드레일 적용
              • 작업 폴더 밖 쓰기 차단 완성 및 OS 수준 격리 설계
              • 명령어 허용 목록 기반 정책 엔진
              • 산출물/로그 내 시크릿(API 키/비밀번호) 자동 마스킹
              • 위변조 방지 보안 감사 로그(Audit Trail)
```

---

## 1. 🌐 더 많은 AI 지원을 위한 어댑터 생태계 확장 (Expanding Adapters)

### 1.1 배경 및 목표
현재 Claude Code, Google Antigravity, OpenAI Codex CLI와 OpenRouter 내장 에이전트를 지원합니다. 글로벌 오픈소스 생태계와 상용 도구에서 빠르게 등장하는 다양한 AI 코딩 도구를 플러그인 방식으로 손쉽게 연결할 수 있도록 어댑터 계층을 확장합니다.

> Aider는 지원 계획이 없어 전용 어댑터를 제거했습니다.

### 1.2 주요 추진 과제
- **상용 AI CLI 어댑터 추가**:
  - **GitHub Copilot CLI (`gh copilot`)**: GitHub 생태계 및 엔터프라이즈 라이선스 사용자 환경 연동
  - **Cursor / Windsurf Headless CLI**: 차세대 AI 코드 편집기의 백엔드 CLI 엔진 결합
- **OpenAI 호환 API 내장 에이전트 고도화** (`adapter: "openrouter"`):
  - ✅ OpenRouter와 `base_url` 지정을 통한 Ollama / vLLM / llama.cpp 등 로컬·사내 폐쇄망 모델 연결 (외부 CLI 없이 하네스가 도구를 직접 실행)
  - ✅ 도구 권한 등급(`tools: none | read | full`), 작업 폴더 격리, `run_command` 허용 목록
  - 긴 대화 요약·압축, 토큰 단위 스트리밍, 재시도 및 fallback 모델
  - 웹 UI의 모델 선택·도구 권한 설정 지원
- **플러그인 기반 커스텀 어댑터 SDK (Custom Adapter SDK)**:
  - 사용자가 사내 자체 AI CLI나 독자 래퍼 스크립트를 YAML 설정이나 간단한 Python 클래스 정의만으로 즉시 ModueHarness에 등록할 수 있는 표준 규격 인터페이스 제공

---

## 2. 🌍 원격지 로그인 AI 연결 및 분산 협업 노드 확장 (Remote AI Node Federation)

### 2.1 배경 및 목표
모든 AI CLI가 사용자의 로컬 컴퓨터 한 대에 설치·로그인되어 있을 필요 없이, 각기 다른 개발 서버, 클라우드 VM, 또는 사내 원격 장비에 개별적으로 로그인된 AI들을 네트워크를 통해 하나의 하네스 팀으로 결합하는 **분산 오케스트레이션(Distributed Multi-Agent Orchestration)** 환경을 구축합니다.

### 2.2 주요 추진 과제
- **SSH / Remote Daemon Bridge**:
  - SSH 터널링 또는 경량 하네스 원격 에이전트(Daemon)를 통해 원격 머신에서 실행 중인 AI CLI에 명령을 디스패치하고 결과를 실시간 스트리밍으로 회수
- **원격 인증 세션 및 크레딧 브릿지**:
  - 특정 서버에만 기업용 라이선스나 계정이 인증되어 있는 경우, 로컬 환경에서 해당 머신의 인증 세션을 안전하게 프록시하여 작업을 위임
- **분산 블랙보드 동기화 (Distributed Blackboard Sync)**:
  - 로컬 지휘관(Conductor)과 원격 워커 노드 간의 상태(`state.json`), 태스크(`tasks/`), 산출물(`artifacts/`)을 gRPC/WebSocket 기반으로 실시간 양방향 동기화
- **이기종 하이브리드 팀 구성**:
  - 예: 고성능 클라우드 VM의 상위 모델이 아키텍처 기획 및 종합 검토를 수행하고, 사내 온프레미스 원격 서버의 GPU 모델이 단위 테스트 구현을 수행하는 하이브리드 협업 파이프라인 실현

---

## 3. 🛡️ 엔터프라이즈급 보안 향상 분석 및 안전 가드레일 적용 (Security & Guardrails)

### 3.1 배경 및 목표
자율 AI 에이전트들이 셸 명령어를 실행하고 프로젝트 코드를 직접 수정하는 과정에서 발생할 수 있는 악성 코드 주입, 비인가 파일 접근, 환경 파괴 및 기밀 유출 위험을 원천 차단하는 다층 보안 체계를 도입합니다.

### 3.2 현재 상태: 작업 폴더 밖 쓰기 차단 ([#3](https://github.com/jaenimi-dev/ModueHarness/issues/3))

에이전트가 배정된 프로젝트 폴더(`projects/<project>/`) 밖, 특히 하네스 저장소 자체에 파일을 쓴 사고(#3) 이후, CLI별로 실제 실행해 확인하고 막을 수 있는 경로를 막았습니다.

| 에이전트 | 파일 도구로 밖에 쓰기 | 셸로 밖에 쓰기 | 방식 |
| :--- | :--- | :--- | :--- |
| Antigravity | ✅ 차단 | ✅ 차단 | `--sandbox` + 실행 전 전역 `permissions.deny` 자동 설치 |
| Claude Code | ✅ 차단 | ❌ 미차단 | 실행마다 `--settings`로 `Edit(//...)` deny 규칙 주입 |
| Codex | ✅ 차단 | ✅ 차단 | `--sandbox workspace-write` (칠판 폴더는 `--add-dir`로 허용) |
| OpenRouter 내장 에이전트 | ✅ 차단 | ✅ 차단 | 하네스가 모든 경로를 검사, `run_command`는 허용 목록 |
| 탐지 (전체) | 사후 경고 | 사후 경고 | 작업 종료 후 폴더 밖 변경 파일 보고 (#4) |

Antigravity와 Claude의 deny 규칙은 **보호할 경로를 나열**하는 방식입니다. 보호 대상은 하네스 저장소의 최상위 항목(`projects/`, `blackboard/` 제외)과 민감한 홈 경로입니다.

### 3.3 주요 추진 과제

- **작업 폴더 밖 쓰기 차단 완성 (보안 설계 예정)**:
  - **Claude의 셸(Bash) 쓰기 차단**: Claude Code 샌드박스 연동 (Linux는 `bubblewrap`, `socat` 필요)
  - **목록에 없는 경로 보호**: Antigravity·Claude는 나열한 경로만 막으므로, 하네스 저장소 밖의 다른 폴더까지 막는 방식 설계
  - **Antigravity 전역 설정 수정 방식 재검토**: agy에 실행별 설정 수단이 없어 사용자의 전역 설정을 수정하고 있으며, 하네스 밖 agy 사용에도 영향을 줌
  - **사후 탐지(#4) 보강**: 숨김 파일, 파일 삭제, 하네스 저장소 밖 쓰기를 탐지하고, 이탈 시 작업을 실패 처리하는 옵션
  - **Git Worktree 격리 정리**: `isolation: worktree` 스텝의 산출물이 worktree 제거 시 유실되는 문제를 고치고, README의 격리 설명을 실제 동작에 맞게 수정
- **샌드박스 및 컨테이너 격리 (Containerized Sandboxing)**:
  - Docker, Podman 또는 Linux cgroups/namespace를 활용하여 워커 AI의 실행 환경을 호스트 시스템과 완벽하게 격리
  - CLI별 규칙에 의존하지 않고 지정된 프로젝트 작업 디렉토리(`projects/<project>/`)와 칠판 외의 호스트 파일시스템 및 개인 정보 디렉토리 접근 원천 봉쇄
- **명령어 정책 엔진 (Command Policy Engine)**:
  - 차단 목록은 우회가 쉬우므로, 프로젝트 단위 **명령어 허용 목록**을 기본으로 하는 정책 엔진 (OpenRouter 내장 에이전트의 `run_command` 허용 목록을 다른 에이전트로 확장)
  - 에이전트별 권한 등급제(읽기 전용, 워크스페이스 쓰기, 관리자 권한) 적용
- **시크릿 & 개인정보 유출 방지 필터 (Secret Leak Prevention)**:
  - ✅ 블랙보드 교환 산출물, 종합 보고서, 실행 로그, 작업 기록, 진행 알림에서 API 키·토큰·패스워드·개인 키를 자동 마스킹 (설정된 키 값 + 알려진 키 형식)
  - 개인식별정보(PII: 이메일, 전화번호 등) 검출과 사용자 정의 마스킹 규칙
- **위변조 불가능한 보안 감사 로그 (Tamper-evident Audit Trail)**:
  - 언제, 어떤 AI가, 어떤 근거로, 어떤 파일이나 시스템 자원에 접근·수정했는지 전 과정을 타임스탬프 기반의 감사 로그(`audit.jsonl`)로 영구 보존하여 규정 준수(Compliance) 충족

---

## 📅 로드맵 마일스톤 개요

| 단계 | 목표 마일스톤 | 중점 영역 | 상태 |
| :--- | :--- | :--- | :--- |
| **Phase 1 (단기)** | 보안 기본 가드레일 | 작업 폴더 밖 쓰기 차단(CLI별 규칙·샌드박스), OpenRouter 내장 에이전트, 시크릿 마스킹 | 완료 (PII 검출은 후속) |
| **Phase 2 (중기)** | 보안 설계 및 원격 노드 브릿지 | 작업 폴더 밖 쓰기 차단 완성(3.3), 명령어 허용 목록 정책 엔진, SSH 기반 원격 AI 실행 브릿지, 분산 칠판 동기화 | 예정 |
| **Phase 3 (장기)** | 엔터프라이즈 컨테이너 샌드박스 및 규정 준수 | Docker/Podman 격리 실행 환경, 커스텀 어댑터 SDK, 정밀 감사 로그 체계 | 예정 |

---

*ModueHarness는 개발자의 생산성을 극대화하면서도 신뢰성과 안전성을 보장하는 미래지향적 Multi-AI 협업 환경을 지속적으로 발전시켜 나가겠습니다.*
