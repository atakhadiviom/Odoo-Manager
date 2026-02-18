"""
Git utility functions for Odoo Manager.
"""

import subprocess
from pathlib import Path
from typing import Optional


def run_git_command(
    cwd: Path, *args: str, capture: bool = True, check: bool = True
) -> Optional[str]:
    """Run a git command in the specified directory.

    Args:
        cwd: Working directory for the command.
        *args: Git command arguments (e.g., 'status', 'branch', '-v').
        capture: Whether to capture output.
        check: Whether to raise on non-zero exit.

    Returns:
        Command output if capture=True, None otherwise.

    Raises:
        subprocess.CalledProcessError: If check=True and command fails.
    """
    cmd = ["git"] + list(args)

    kwargs = {"cwd": cwd, "text": True}
    if capture:
        kwargs["capture_output"] = True

    result = subprocess.run(cmd, **kwargs)

    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)

    if capture:
        return result.stdout.strip()

    return None


def get_git_diff(cwd: Path, staged: bool = False) -> str:
    """Get git diff output.

    Args:
        cwd: Working directory.
        staged: If True, show staged changes. Otherwise, show unstaged.

    Returns:
        Diff output.
    """
    args = ["diff"]
    if staged:
        args.append("--staged")

    return run_git_command(cwd, *args) or ""


def get_git_status(cwd: Path) -> dict:
    """Get git status as a dictionary.

    Args:
        cwd: Working directory.

    Returns:
        Dictionary with status information.
    """
    try:
        output = run_git_command(cwd, "status", "--porcelain") or ""
    except subprocess.CalledProcessError:
        output = ""

    staged = []
    modified = []
    untracked = []
    conflicted = []

    for line in output.split("\n"):
        if not line:
            continue

        status = line[:2]
        path = line[3:]

        if status[0] in ("M", "A", "D", "R", "C"):
            staged.append(path)
        if status[1] == "M":
            modified.append(path)
        if status == "??":
            untracked.append(path)
        if status in ("DD", "AU", "UD", "UA", "DU", "AA", "UU"):
            conflicted.append(path)

    return {
        "staged": staged,
        "modified": modified,
        "untracked": untracked,
        "conflicted": conflicted,
        "clean": len(staged) == 0 and len(modified) == 0 and len(conflicted) == 0,
    }


def get_changed_files(cwd: Path, branch: Optional[str] = None) -> list[str]:
    """Get list of changed files compared to a branch.

    Args:
        cwd: Working directory.
        branch: Branch to compare against. Defaults to main/master.

    Returns:
        List of changed file paths.
    """
    if branch is None:
        # Detect default branch
        try:
            if run_git_command(cwd, "rev-parse", "--verify", "main") is not None:
                branch = "main"
            else:
                branch = "master"
        except subprocess.CalledProcessError:
            branch = "HEAD~10"  # Fallback to last 10 commits

    try:
        output = run_git_command(cwd, "diff", "--name-only", f"HEAD...{branch}")
        return [f for f in output.split("\n") if f] if output else []
    except subprocess.CalledProcessError:
        return []


def format_commit_message(message: str, max_length: int = 80) -> str:
    """Format a commit message for display.

    Args:
        message: Raw commit message.
        max_length: Maximum length to return.

    Returns:
        Formatted commit message.
    """
    # Get first line only
    first_line = message.split("\n")[0].strip()

    if len(first_line) > max_length:
        return first_line[: max_length - 3] + "..."

    return first_line


def validate_git_url(url: str) -> bool:
    """Validate a git repository URL.

    Args:
        url: URL to validate.

    Returns:
        True if URL appears to be valid.
    """
    if not url:
        return False

    # Common git URL patterns
    patterns = [
        ("https://", False),
        ("http://", False),
        ("git@", False),
        ("git://", False),
        ("file://", False),
        ("/", True),  # Local path
    ]

    for pattern, is_exact in patterns:
        if is_exact:
            if url.startswith(pattern):
                return True
        else:
            if url.startswith(pattern):
                # Check for common git repo patterns
                if ".git" in url or "/" in url.split("://")[-1]:
                    return True

    return False


def find_git_root(cwd: Path) -> Optional[Path]:
    """Find the root of the git repository containing the given path.

    Args:
        cwd: Starting directory.

    Returns:
        Path to git root, or None if not in a git repo.
    """
    current = cwd.resolve()

    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent

    return None


def get_git_remote_url(cwd: Path, remote: str = "origin") -> Optional[str]:
    """Get the URL of a git remote.

    Args:
        cwd: Working directory.
        remote: Remote name.

    Returns:
        Remote URL or None if not found.
    """
    try:
        return run_git_command(cwd, "remote", "get-url", remote)
    except subprocess.CalledProcessError:
        return None


def get_git_branch_info(cwd: Path) -> dict:
    """Get detailed branch information.

    Args:
        cwd: Working directory.

    Returns:
        Dictionary with branch information.
    """
    try:
        current = run_git_command(cwd, "branch", "--show-current")
    except subprocess.CalledProcessError:
        current = None

    try:
        # Get tracking branch
        tracking = run_git_command(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    except subprocess.CalledProcessError:
        tracking = None

    try:
        ahead = run_git_command(cwd, "rev-list", "--count", "@{u}..HEAD")
        ahead = int(ahead) if ahead else 0
    except subprocess.CalledProcessError:
        ahead = 0

    try:
        behind = run_git_command(cwd, "rev-list", "--count", "HEAD..@{u}")
        behind = int(behind) if behind else 0
    except subprocess.CalledProcessError:
        behind = 0

    return {
        "current": current,
        "tracking": tracking,
        "ahead": ahead,
        "behind": behind,
        "has_changes": ahead > 0 or behind > 0,
    }
