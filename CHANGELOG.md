# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
