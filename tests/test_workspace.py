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
