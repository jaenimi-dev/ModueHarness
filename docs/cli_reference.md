# ModueHarness CLI 명령어 레퍼런스 (CLI Reference)

ModueHarness CLI 도구의 전체 명령어 및 옵션 가이드입니다.

---

## 1. `init`
공용 칠판(`blackboard/`) 디렉터리와 초기 세션 상태 파일을 생성합니다.

```bash
python3 -m modue_harness.cli init [--dir <blackboard_path>]
```

- `--dir`, `-d`: 블랙보드 폴더 경로 (기본값: `blackboard`)

---

## 2. `status`
현재 공용 칠판의 워크플로우 진행 상태, 태스크 큐 목록 및 생성된 아티팩트를 출력합니다.

```bash
python3 -m modue_harness.cli status [--dir <blackboard_path>]
```

---

## 3. `run`
YAML 또는 JSON 워크플로우 명세 파일을 실행합니다.

```bash
python3 -m modue_harness.cli run --config <workflow.yaml> [OPTIONS]
```

### 옵션
- `--config`, `-c` *(필수)*: 실행할 워크플로우 명세 파일 경로
- `--agents`, `-a`: AI 팀 명세 파일 경로 (워크플로우 내 `agents_file`을 오버라이드)
- `--dir`, `-d`: 블랙보드 폴더 경로 (기본값: `blackboard`)
- `--report`, `-r`: 실행 완료 후 마크다운 실행 결과 보고서를 저장할 경로 (예: `report.md`)

### 예시
```bash
# 기본 실행
python3 -m modue_harness.cli run -c examples/feature_workflow.yaml

# AI 팀 교체 및 보고서 생성
python3 -m modue_harness.cli run -c workflow.yaml -a local_agents.yaml -r report.md
```

---

## 4. `debate`
두 개 이상의 AI CLI 간의 토론 및 판정관 합의 워크플로우를 즉시 실행합니다.

```bash
python3 -m modue_harness.cli debate --topic <TOPIC> [OPTIONS]
```

### 옵션
- `--topic`, `-t` *(필수)*: 토론할 주제 또는 설계 문제
- `--proposer`: 제안자 에이전트 어댑터 (기본값: `claude`)
- `--challenger`: 도전자/비판자 에이전트 어댑터 (기본값: `agy`)
- `--judge`: 판정관 에이전트 어댑터 (기본값: `claude`)
- `--rounds`: 토론 라운드 수 (기본값: 2)
- `--dir`, `-d`: 블랙보드 폴더 경로 (기본값: `blackboard`)

### 예시
```bash
python3 -m modue_harness.cli debate \
  --topic "Microservices vs Modular Monolith" \
  --proposer claude \
  --challenger agy \
  --judge claude \
  --rounds 2
```
결과는 `blackboard/artifacts/consensus.md`에 저장됩니다.
