"""Tests for GitWorkspaceManager."""

from pathlib import Path
import subprocess
import pytest

from modue_harness.workspace.manager import GitWorkspaceManager


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Fixture providing an initialized git repository."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), check=True)

    # Initial commit
    file1 = repo / "README.md"
    file1.write_text("# Initial", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(repo), check=True)

    return repo


def test_git_repo_detection(temp_git_repo: Path, tmp_path: Path):
    """Verify is_git_repo accurately identifies git repos."""
    mgr = GitWorkspaceManager(temp_git_repo)
    assert mgr.is_git_repo()

    non_git_mgr = GitWorkspaceManager(tmp_path / "not_a_repo")
    assert not non_git_mgr.is_git_repo()


def test_git_snapshot_and_rollback(temp_git_repo: Path):
    """Verify snapshot capture and rollback capability."""
    mgr = GitWorkspaceManager(temp_git_repo)
    readme = temp_git_repo / "README.md"

    # Make modification
    readme.write_text("# Modified Content", encoding="utf-8")
    snapshot = mgr.create_snapshot("test_stash")
    assert snapshot.stash_ref is not None

    # Now make another bad edit
    readme.write_text("# Bad Destructive Edit", encoding="utf-8")

    # Roll back
    success = mgr.rollback_snapshot(snapshot)
    assert success
    assert readme.read_text(encoding="utf-8") == "# Modified Content"


def test_git_worktree_lifecycle(temp_git_repo: Path):
    """Verify worktree creation, isolation, and removal."""
    mgr = GitWorkspaceManager(temp_git_repo)
    worktree_path = temp_git_repo / ".worktrees" / "feature_branch"

    created_path = mgr.create_worktree("harness/feature_test", worktree_path)
    assert created_path.exists()
    assert (created_path / ".git").exists()

    # Create a file inside isolated worktree
    new_file = created_path / "isolated.txt"
    new_file.write_text("created inside worktree", encoding="utf-8")

    # Main repo should NOT see the file
    assert not (temp_git_repo / "isolated.txt").exists()

    # Remove worktree
    removed = mgr.remove_worktree(created_path)
    assert removed
    assert not created_path.exists()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True, text=True).stdout.strip()


def test_commit_worktree_keeps_changes_on_branch(temp_git_repo: Path):
    mgr = GitWorkspaceManager(temp_git_repo)
    wt = mgr.create_worktree("harness/keep", temp_git_repo / ".wt" / "keep")
    (wt / "result.py").write_text("print('agent output')\n", encoding="utf-8")

    sha = mgr.commit_worktree(wt, "harness: step 'keep'")
    assert mgr.remove_worktree(wt)

    assert sha and not wt.exists()
    assert _git(temp_git_repo, "show", "harness/keep:result.py") == "print('agent output')"
    # 원래 작업 트리는 오염되지 않는다.
    assert not (temp_git_repo / "result.py").exists()


def test_commit_worktree_returns_none_when_clean(temp_git_repo: Path):
    mgr = GitWorkspaceManager(temp_git_repo)
    wt = mgr.create_worktree("harness/clean", temp_git_repo / ".wt" / "clean")
    assert mgr.commit_worktree(wt, "noop") is None


def test_commit_worktree_ignores_signing_and_missing_identity(temp_git_repo: Path):
    subprocess.run(["git", "config", "commit.gpgsign", "true"], cwd=str(temp_git_repo), check=True)
    subprocess.run(["git", "config", "--unset", "user.name"], cwd=str(temp_git_repo), check=True)
    mgr = GitWorkspaceManager(temp_git_repo)
    wt = mgr.create_worktree("harness/sign", temp_git_repo / ".wt" / "sign")
    (wt / "a.txt").write_text("a", encoding="utf-8")

    assert mgr.commit_worktree(wt, "harness: sign") is not None
    assert _git(temp_git_repo, "log", "-1", "--format=%an", "harness/sign") == "ModueHarness"


def test_pipeline_worktree_step_output_is_not_lost(temp_git_repo: Path):
    """Regression: isolation: worktree used to delete everything the agent wrote."""
    import sys

    from modue_harness.adapters.generic import GenericCLIAdapter
    from modue_harness.core.blackboard import Blackboard
    from modue_harness.engine.pipeline import PipelineRunner
    from modue_harness.engine.workflow import WorkflowAgentConfig, WorkflowConfig, WorkflowStepConfig

    writer = GenericCLIAdapter(
        name="dev",
        command=sys.executable,
        default_args=["-c", "open('feature.py','w').write('x = 1\\n')"],
    )
    config = WorkflowConfig(
        name="wt",
        agents={"dev": WorkflowAgentConfig(name="dev")},
        steps=[WorkflowStepConfig(id="impl", agent="dev", instruction="write", isolation="worktree")],
    )
    board = Blackboard(temp_git_repo.parent / "board")
    board.initialize()
    runner = PipelineRunner(
        config=config, blackboard=board, workspace_dir=temp_git_repo, adapters_override={"dev": writer}
    )

    step = runner.run()["steps"][0]

    assert step["is_success"], step
    assert step["worktree_branch"] == "harness/impl"
    assert step["worktree_commit"]
    assert _git(temp_git_repo, "show", "harness/impl:feature.py") == "x = 1"
    assert not (temp_git_repo / ".modue_worktrees" / "impl").exists()
    assert not (temp_git_repo / "feature.py").exists()
