# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-09-18

### Added
- **Workspace Isolation & Git Management (`workspace/`)**:
  - `GitWorkspaceManager` supporting isolated worktree creation (`git worktree add -b harness/...`), removal, and pruning.
  - Temporary stash snapshots and rollback mechanism (`create_snapshot()`, `rollback_snapshot()`).
  - Git diff extraction and modified files tracking.
- **Process Supervisor & Safety Watchdog (`core/supervisor.py`)**:
  - `ProcessSupervisor` with activity monitoring and stall detection.
  - Infinite loop / repeating output runaway detection.
  - Graceful subprocess termination (SIGTERM followed by SIGKILL).
  - Human-in-the-loop checkpoint support (`requires_approval` with interactive approval callback).

## [0.2.0] - 2026-09-18

### Added
- **Lifecycle Event System (`core/events.py`)**:
  - `EventBus` pub/sub broker and `HarnessEvent` records.
  - Lifecycle events for workflow start/completion, step start/failure, artifact production, and task status changes.
- **Enhanced Blackboard**:
  - Artifact metadata persistence (`.meta.json`) tracking author agent, file size, and creation timestamp.
  - Full EventBus integration in Blackboard operations.
- **Advanced CLI Adapters**:
  - Real-time line-by-line streaming output via `execute_stream()`.
  - Model selection and system instruction options for `ClaudeCLIAdapter`, `AGYCLIAdapter`, and `AiderCLIAdapter`.
- **Conditional & Resilient Pipeline Execution**:
  - Preconditions support (`condition: artifact_exists:<path>`, `not_exists:<path>`).
  - Dynamic artifact variable interpolation (`${artifact:path}`).
  - Step automatic retry (`retry_count`) and fallback agent delegation (`fallback_agent`).

## [0.1.0] - 2026-09-17

### Added
- **Multi-AI CLI Adapter Layer**:
  - `BaseCLIAdapter` with subprocess management, timeout guards, and ANSI sequence stripping.
  - Preconfigured adapters: `ClaudeCLIAdapter`, `AGYCLIAdapter`, `AiderCLIAdapter`, and extensible `GenericCLIAdapter`.
  - Adapter factory `create_adapter()`.
- **Shared Blackboard System (`blackboard/`)**:
  - `Blackboard` workspace coordinator managing `tasks/`, `artifacts/`, `logs/`, and `state.json`.
  - Atomic state updates, task status transitions, and artifact exchange.
- **Workflow & Orchestration Engine**:
  - `WorkflowConfig` supporting YAML & JSON workflow definitions.
  - `PipelineRunner` executing sequential multi-AI CLI pipelines with artifact handoff.
- **CLI Subcommands**:
  - `modue-harness init`: Initialize blackboard workspace.
  - `modue-harness status`: View current blackboard tasks and session state.
  - `modue-harness run`: Execute multi-AI workflows from configuration files.

## [0.0.0] - 2026-09-17

### Added
- Initial project scaffold structure.
- Basic CLI entrypoint (`modue-harness`).
- Core harness base interface (`BaseHarness`, `HarnessConfig`).
- Initial unit test suite with pytest.
