# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-09-20

### Added
- **Automated All-in-One Installer Scripts (`install.sh`, `install.ps1`)**:
  - One-line / automated setup scripts for Linux/macOS and Windows PowerShell.
  - Automatically fetches/updates repo via Git or GitHub CLI (`gh`), installs all dependencies (`pip install -e ".[all]"`), and runs validation tests.
- **OpenAI ChatGPT Codex CLI Adapter & Web UI Integration**:
  - Dedicated `CodexCLIAdapter` supporting headless `codex exec`, sandbox permissions (`--sandbox workspace-write`), dynamic model configuration.
  - Web UI adapter selection (`codex`) with emerald styling and latest model presets (`gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`).
- **ChatGPT Codex CLI Guide (`docs/codex_guide.md`)**:
  - Comprehensive installation, authentication (`codex login`), sandbox permissions, PowerShell restart notices, and ModueHarness integration manual.
- **Project Deletion Feature**:
  - Web UI project deletion button in header with confirmation modal.
  - Project directory and isolated blackboard directory cleanup (`delete_project` API).
  - CLI `projects --delete <project_name>` support.
- **Job History Compact Card & Detail Dialog**:
  - Clean 3-row compact job cards preventing text overflow.
  - "자세히 보기" (View Details) modal dialog displaying full command, execution stage, formatted logs, and error details.

### Fixed
- **Stream Output Improvements**:
  - Limited CLI command preview display to prevent full prompt/JSON instruction leaks into live stream.
  - Expanded subtask instruction preview length from 50/60 to 200 characters to prevent unwanted truncation.
- **UI Overflow & Tab Layout Fixes**:
  - Made header project dropdown dense and outlined to fit cleanly within 52px header bar.
  - Resolved right panel and tab headers clipping issue with responsive flexbox proportions and dense tab styling.
  - Removed redundant English suffixes in Korean tab labels.

## [0.7.0] - 2026-09-20

### Added
- **Project-isolated Blackboard**:
  - Independent blackboard workspaces per project (`blackboard/<project_name>/`).
  - Automatic synchronization and refresh across project switches.
- **Process Cancellation & Process Group Termination**:
  - Subprocess cancellation with SIGTERM/SIGKILL across process groups.

## [0.6.0] - 2026-09-20

### Added
- **Google Antigravity (`agy` / `antigravity`) CLI Adapter**:
  - Full support for Google Antigravity CLI as an autonomous engineering agent (`AGYCLIAdapter`).
  - Auto-enables `--dangerously-skip-permissions` to eliminate interactive blocking prompts during autonomous runs.
  - Supports model selection (`gemini-3.8-flash-high`, `gemini-3.1-pro-high`, etc.) and reasoning effort levels (`low`, `medium`, `high`).
  - OS-aware binary discovery on Linux/macOS and Windows (`%LOCALAPPDATA%\agy\bin\agy.exe`).
  - Comprehensive documentation guide in `docs/antigravity_guide.md`.
- **Dynamic AI Model & Reasoning Effort Controls**:
  - REPL slash commands: `/model [agent] [model]` and `/effort [agent] [level]`.
  - CLI execution flags: `-m, --model` and `-e, --effort`.
  - Claude and Antigravity multi-agent team hybrid configurations.
- **Unabbreviated CLI Command Output & Inspection**:
  - Real-time transparent terminal output of full CLI commands (`💻 CLI 실행: ...`) without prompt truncation.
  - `/cmd` (and `/last-cmd`) REPL command to inspect complete execution histories across phases.
- **Detailed Failure Reason Diagnostics**:
  - Automatic extraction of subprocess stderr/stdout (up to 5 lines) on non-zero exit codes.
  - Real-time streaming, final summary reports, and `/jobs` output displaying `❌ [실패 상세 원인]` and `❌ 오류 상세: ...`.
- **Configurable Session Timeout**:
  - Removed arbitrary 300s hardcoded execution timeout (unlimited by default for long/deep reasoning tasks).
  - Added `/timeout [seconds|off]` REPL command and `-t, --timeout` CLI option.

## [0.5.0] - 2026-09-20

### Added
- **Interactive REPL Mode (`-i` / `--interactive`)**:
  - Interactive command-line REPL loop allowing users to direct AI agents with ad-hoc instructions without predefined workflow YAML files.
  - Built-in slash commands: `/help`, `/status`, `/artifacts`, `/agents`, `/run`, `/clean`, `/jobs`, `/cancel`, `/bg`, `/exit`, `/quit`.
- **Project Workspace & Blackboard Separation (`-P` / `--project-name`)**:
  - Separation of code generation into isolated project workspaces (`projects/<project-name>/`).
  - Preserved `blackboard/` purely for inter-agent context sharing, specs, tasks, and state.
- **Live Progress Streaming (`core/events.py`, `cli.py`)**:
  - Terminal real-time event streaming during interactive and CLI executions.
  - Immediate visual feedback on workflow status, agent invocations, and artifact updates.
- **Background Async Job Management**:
  - Support for executing tasks asynchronously in background with trailing `&` or `/bg <command>`.
  - Non-blocking REPL prompt allowing concurrent command entry while tasks execute.
  - `/jobs` to list active/completed background tasks and `/cancel <job_id>` to abort executions.
- **Direct Entrypoint Script (`run.py`)**:
  - Convenient root launcher resolving Python package pathing without requiring prior `pip install -e .`.

## [0.4.0] - 2026-09-18

### Added
- **Leader-Worker Conductor Topology (`engine/conductor.py`)**:
  - `ConductorRunner` enabling dynamic goal breakdown into worker subtasks.
  - Automatic JSON task extraction, worker delegation, and final Conductor synthesis.
- **Debate & Consensus Topology (`engine/debate.py`)**:
  - `DebateRunner` for multi-round adversarial or collaborative debate between Proposer and Challenger.
  - Impartial Judge/Arbiter agent evaluating arguments and forging final `consensus.md`.
- **Plugin Architecture & Lifecycle Hooks (`plugins/`)**:
  - `BasePlugin` and `PluginManager` with event hooks across workflow, step, and artifact lifecycles.
  - `MarkdownReportPlugin` automatically generating formatted markdown execution summaries.
- **CLI Enhancements**:
  - Added `modue-harness debate` subcommand for direct multi-AI debate execution.
  - Added `--report` flag to `modue-harness run` for automated execution report generation.

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
