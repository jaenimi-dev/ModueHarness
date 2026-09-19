# ModueHarness 명세 작성 가이드 (Specifications Guide)

ModueHarness는 정적 파이프라인 및 복잡한 배치 자동화를 위해 **AI 팀 명세(`agents.yaml`)**와 **작업/할 일 명세(`workflow.yaml`)**의 분리 구성을 지원합니다.

> 💡 **명세 파일이 항상 필요한가요? (자연어 대화형 모드 vs 워크플로우)**:  
> - **대화형 CLI 및 직접 명령 모드 (`modue-harness -i` 또는 `modue-harness "<명령어>" -P <프로젝트명>`)**:  
>   `workflow.yaml` 파일을 **작성할 필요가 전혀 없습니다**. 시스템에 설치된 AI CLI를 자동 감지하여 Conductor(Leader)가 명령을 해석하고 Worker들이 `projects/<프로젝트명>/`에 직접 구현합니다.
> - **정적 파이프라인 모드 (`modue-harness run -c workflow.yaml`)**:  
>   CI/CD 연동, 정형화된 다단계 조건부 릴레이, 특정 스텝 재시도 및 승인 체크포인트가 필요한 경우에 아래 가이드에 따라 명세 파일을 작성합니다.

> 📁 **설정 파일 위치 권장사항 (`config/`)**:  
> 명세 파일들은 프로젝트 내 `config/` 폴더(`config/agents.yaml`, `config/workflow.yaml`)에 관리하는 것을 권장합니다.  
> `config/` 폴더는 `.gitignore`가 설정되어 있어 예제 템플릿(`*.example.yaml`) 외의 실제 설정 파일은 GitHub에 커밋되지 않고 로컬에 안전하게 보관됩니다.

---

## 1. AI 팀 명세 (`agents.yaml`)

어떤 AI CLI 도구(Claude, AGY, Aider 등)와 모델, 권한, 역할을 가진 팀원들로 구성할지 선언합니다.

```yaml
version: "0.5.0"
name: "modue-engineering-team"

agents:
  planner:
    adapter: "claude"                  # claude, antigravity (agy), aider, generic
    command: "claude"                  # 실행할 CLI 명령어
    args: ["--permission-mode", "auto"] # 추가 실행 인자 (프롬프트 멈춤 방지)
    model: "claude-3-7-sonnet-latest"  # 선택적 모델 지정 (sonnet, opus, haiku 등)
    effort: "high"                     # 추론 노력 (low, medium, high, max)
    role: "System Architect"           # 역할 설명
    system_instruction: "You are the lead architect..."

  coder:
    adapter: "antigravity"             # 또는 agy
    command: "agy"
    args: ["--dangerously-skip-permissions"]
    model: "gemini-3.8-flash-high"
    effort: "medium"
    role: "Software Engineer"

  reviewer:
    adapter: "claude"
    command: "claude"
    args: ["--permission-mode", "auto"]
    model: "claude-3-7-sonnet-latest"
    effort: "high"
    role: "Quality Reviewer"
```

---

## 2. 작업/할 일 명세 (`workflow.yaml`)

실제 프로젝트에서 수행할 태스크, 산출물 입출력 연계, 실행 조건, 격리 옵션을 정의합니다.

```yaml
version: "0.5.0"
name: "data-pipeline-feature"

# 사용할 AI 팀 명세 파일 지정 (상대 경로 가능)
agents_file: "agents.yaml"

workflow:
  topology: "pipeline"                 # pipeline, conductor, debate
  timeout_per_step: 300                # 기본 타임아웃(초)
  isolation: "worktree"                # worktree 또는 미지정
  steps:
    - id: "design_system"
      agent: "planner"
      instruction: "Draft system architecture design."
      output_artifact: "architecture.md"

    - id: "build_code"
      agent: "coder"
      condition: "artifact_exists:architecture.md"  # 선행 조건 확인
      input_artifacts: ["architecture.md"]         # 선행 산출물 주입
      instruction: "Implement components for: ${artifact:architecture.md}"
      output_artifact: "components.py"
      retry_count: 1                               # 실패 시 1회 재시도
      fallback_agent: "planner"                    # 재시도 실패 시 대체 에이전트

    - id: "review_build"
      agent: "reviewer"
      input_artifacts: ["components.py"]
      instruction: "Review code quality and security."
      output_artifact: "review.md"
      requires_approval: true                      # 사용자 승인 체크포인트
```

---

## 3. 핵심 기능 설명

- **조건부 실행 (`condition`)**:
  - `artifact_exists:<path>`: 해당 아티팩트가 존재할 때만 실행 (없으면 건너뜀).
  - `not_exists:<path>`: 아티팩트가 없을 때만 실행.
- **템플릿 변수 치환**:
  - `${artifact:<path>}`: 해당 아티팩트의 텍스트 내용이 지시문에 자동으로 인라인 치환됩니다.
- **격리 모드 (`isolation: "worktree"`)**:
  - 해당 스텝은 별도의 임시 `git worktree`에서 실행되어 메인 작업 디렉터리를 오염시키지 않습니다.
- **저장소 분리 원칙**:
  - 모든 워크플로우 진행 상황, 태스크, 교환 산출물은 `blackboard/`에 저장되며, 개발 코드는 대상 프로젝트 디렉터리에 반영됩니다.
