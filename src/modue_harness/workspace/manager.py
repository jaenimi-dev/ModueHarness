"""Git Workspace and Worktree isolation manager."""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import List, Optional


@dataclass
class Snapshot:
    """Represents a temporary workspace snapshot for rollback."""

    snapshot_id: str
    stash_ref: Optional[str] = None
    created_at: float = 0.0


class GitWorkspaceManager:
    """Manages workspace snapshots and isolated Git worktrees for AI agents."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()

    def is_git_repo(self) -> bool:
        """Check if the target directory is a valid git repository."""
        return (self.repo_root / ".git").exists()

    def _run_git(self, args: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Run a git command safely."""
        return subprocess.run(
            ["git"] + args,
            cwd=str(cwd or self.repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def create_worktree(self, branch_name: str, target_dir: Path) -> Path:
        """Create an isolated git worktree on a specified branch."""
        if not self.is_git_repo():
            raise RuntimeError(f"Directory {self.repo_root} is not a git repository.")

        target_dir = target_dir.resolve()
        target_dir.parent.mkdir(parents=True, exist_ok=True)

        # Check if branch exists
        branch_check = self._run_git(["rev-parse", "--verify", branch_name])
        if branch_check.returncode == 0:
            cmd = ["worktree", "add", str(target_dir), branch_name]
        else:
            cmd = ["worktree", "add", "-b", branch_name, str(target_dir)]

        proc = self._run_git(cmd)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {proc.stderr.strip()}")

        return target_dir

    def remove_worktree(self, target_dir: Path, force: bool = True) -> bool:
        """Remove a git worktree and prune."""
        if not self.is_git_repo():
            return False

        target_dir = target_dir.resolve()
        cmd = ["worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.append(str(target_dir))

        proc = self._run_git(cmd)
        self._run_git(["worktree", "prune"])
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        return proc.returncode == 0

    def create_snapshot(self, message: str = "harness_snapshot") -> Snapshot:
        """Create a temporary git stash snapshot."""
        if not self.is_git_repo():
            return Snapshot(snapshot_id="no_git")

        proc = self._run_git(["stash", "create", message])
        stash_sha = proc.stdout.strip()
        if stash_sha:
            # Store as stash reference
            self._run_git(["stash", "store", "-m", message, stash_sha])
            return Snapshot(snapshot_id=stash_sha, stash_ref=stash_sha)

        return Snapshot(snapshot_id="clean_workspace")

    def rollback_snapshot(self, snapshot: Snapshot) -> bool:
        """Roll back working directory to the captured snapshot state."""
        if not self.is_git_repo() or not snapshot.stash_ref:
            return True

        # Discard untracked / unstaged changes
        self._run_git(["reset", "--hard", "HEAD"])
        self._run_git(["clean", "-fd"])

        # Apply the stashed changes
        proc = self._run_git(["stash", "apply", snapshot.stash_ref])
        return proc.returncode == 0

    def get_diff(self, cwd: Optional[Path] = None) -> str:
        """Return git diff of modified files."""
        if not self.is_git_repo():
            return ""
        proc = self._run_git(["diff", "HEAD"], cwd=cwd)
        return proc.stdout

    def get_modified_files(self, cwd: Optional[Path] = None) -> List[str]:
        """Return list of modified or newly added files."""
        if not self.is_git_repo():
            return []
        proc = self._run_git(["status", "--porcelain"], cwd=cwd)
        lines = proc.stdout.strip().splitlines()
        files = []
        for line in lines:
            if len(line) > 3:
                files.append(line[3:].strip())
        return files
