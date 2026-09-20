# ModueHarness 향후 발전 방향 및 로드맵 (Future Roadmap)

ModueHarness(모두의 하네스)는 Claude Code, Google Antigravity(AGY), OpenAI Codex 등 다양한 AI CLI 도구들을 하나의 유기적인 엔지니어링 팀으로 엮는 오케스트레이션 프레임워크입니다.  
ModueHarness가 더욱 강력하고 안전하며 확장성 높은 엔터프라이즈급 멀티 AI 협업 플랫폼으로 도약하기 위한 **3대 핵심 발전 축(Strategic Pillars)**을 정의합니다.

---

## 🧭 3대 핵심 발전 축 (Three Strategic Pillars)

```
┌────────────────────────────────────────────────────────────────────────┐
│                   ModueHarness 미래 발전 핵심 축                        │
└────────────────────────────────────────────────────────────────────────┘
       │
       ├─ [Pillar 1] 🌐 더 많은 AI 지원을 위한 CLI 어댑터 생태계 확장
       │      • Aider, GitHub Copilot CLI, Cursor/Windsurf CLI 연동
       │      • Ollama, vLLM 등 로컬/사내 폐쇄망 LLM CLI 지원
       │      • 플러그인 기반 커스텀 어댑터 SDK 제공
       │
       ├─ [Pillar 2] 🌍 원격지 로그인 AI 연결 및 분산 협업 노드 확장
       │      • SSH / Remote Agent Bridge를 통한 이기종 서버 AI 연결
       │      • 원격 인증 세션/토큰 프록시 및 브릿지
       │      • 분산 블랙보드 동기화 (Distributed Blackboard Sync)
       │
       └─ [Pillar 3] 🛡️ 엔터프라이즈급 보안 향상 분석 및 안전 가드레일 적용
              • 셸 명령어 사전 시맨틱 분석 및 위험 명령어 자동차단
              • Docker / Linux Namespace 기반 컨테이너형 샌드박스 격리
              • 산출물/로그 내 시크릿(API 키/비밀번호) 자동 마스킹
              • 위변조 방지 보안 감사 로그(Audit Trail)
```

---

## 1. 🌐 더 많은 AI 지원을 위한 CLI 어댑터 생태계 확장 (Expanding CLI Adapters)

### 1.1 배경 및 목표
현재의 Claude Code, Google Antigravity, OpenAI Codex 지원에 머무르지 않고, 글로벌 오픈소스 생태계와 상용 도구에서 빠르게 등장하는 다양한 AI 코딩 CLI를 손쉽게 플러그인 방식으로 연결할 수 있도록 어댑터 계층을 확장합니다.

### 1.2 주요 추진 과제
- **인기 오픈소스 및 상용 AI CLI 어댑터 추가**:
  - **Aider (`aider`)**: Git 커밋 기반 페어 프로그래밍 및 다양한 LLM 백엔드 지원 CLI 어댑터 구현
  - **GitHub Copilot CLI (`gh copilot`)**: GitHub 생태계 및 엔터프라이즈 라이선스 사용자 환경 연동
  - **Cursor / Windsurf Headless CLI**: 차세대 AI 코드 편집기의 백엔드 CLI 엔진 결합
- **로컬 / 폐쇄망 LLM CLI 지원**:
  - **Ollama / vLLM / llama.cpp**: 외부 네트워크 연결이 불가능한 보안 구역이나 사내 온프레미스 GPU 환경의 오픈소스 모델(DeepSeek-Coder, Qwen-Coder, Llama-3-Code 등)을 하네스 팀원으로 투입
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
  - 예: 고성능 클라우드 VM의 Claude 3.7 Sonnet이 아키텍처 기획 및 종합 검토를 수행하고, 사내 온프레미스 원격 서버의 GPU 모델이 단위 테스트 구현을 수행하는 하이브리드 협업 파이프라인 실현

---

## 3. 🛡️ 엔터프라이즈급 보안 향상 분석 및 안전 가드레일 적용 (Security & Guardrails)

### 3.1 배경 및 목표
자율 AI 에이전트들이 셸 명령어를 실행하고 프로젝트 코드를 직접 수정하는 과정에서 발생할 수 있는 악성 코드 주입, 비인가 파일 접근, 환경 파괴 및 기밀 유출 위험을 원천 차단하는 다층 보안 체계를 도입합니다.

### 3.2 주요 추진 과제
- **명령어 시맨틱 가드레일 (Command Semantic Guardrails & Policy Engine)**:
  - AI가 실행하려는 셸 명령어를 사전 정적 분석하여 위험 명령어(`rm -rf /`, 권한 변경 `chmod 777`, 비인가 외부 통신 `curl ... | bash` 등) 자동 차단
  - 프로젝트 단위 명령어 화이트리스트 및 권한 등급제(읽기 전용, 워크스페이스 쓰기 전용, 관리자 권한) 적용
- **샌드박스 및 컨테이너 격리 (Containerized Sandboxing)**:
  - Docker, Podman 또는 Linux cgroups/namespace를 활용하여 워커 AI의 실행 환경을 호스트 시스템과 완벽하게 격리
  - 지정된 프로젝트 작업 디렉토리(`projects/<project>/`) 외의 호스트 파일시스템 및 개인 정보 디렉토리 접근 원천 봉쇄
- **시크릿 & 개인정보 유출 방지 필터 (Secret Leak Prevention)**:
  - 블랙보드 교환 산출물, 종합 보고서, 실행 로그 기록 시 API 키, 패스워드, SSH 키, 개인식별정보(PII)를 자동으로 검출하고 마스킹 처리하는 보안 필터 적용
- **위변조 불가능한 보안 감사 로그 (Tamper-evident Audit Trail)**:
  - 언제, 어떤 AI가, 어떤 근거로, 어떤 파일이나 시스템 자원에 접근·수정했는지 전 과정을 타임스탬프 기반의 감사 로그(`audit.jsonl`)로 영구 보존하여 규정 준수(Compliance) 충족

---

## 📅 로드맵 마일스톤 개요

| 단계 | 목표 마일스톤 | 중점 영역 |
| :--- | :--- | :--- |
| **Phase 1 (단기)** | 어댑터 확장 및 보안 기본 가드레일 | Aider 어댑터 추가, 위험 명령어 정적 차단 필터, 시크릿 마스킹 |
| **Phase 2 (중기)** | 원격 노드 브릿지 및 로컬 LLM 연동 | SSH 기반 원격 AI 실행 브릿지, Ollama/vLLM 어댑터, 분산 칠판 동기화 |
| **Phase 3 (장기)** | 엔터프라이즈 컨테이너 샌드박스 및 규정 준수 | Docker/Podman 격리 실행 환경, 커스텀 어댑터 SDK, 정밀 감사 로그 체계 |

---

*ModueHarness는 개발자의 생산성을 극대화하면서도 신뢰성과 안전성을 보장하는 미래지향적 Multi-AI 협업 환경을 지속적으로 발전시켜 나가겠습니다.*
