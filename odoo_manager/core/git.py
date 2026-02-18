"""
Git repository management for Odoo Manager.
"""

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from git import Repo, GitCommandError, InvalidGitRepositoryError

from odoo_manager.constants import DEFAULT_GIT_REPOS_DIR
from odoo_manager.exceptions import GitError
from odoo_manager.utils.output import success, info, warn


class GitBranchType(Enum):
    """Types of git branches."""

    LOCAL = "local"
    REMOTE = "remote"
    ALL = "all"


@dataclass
class GitRepoInfo:
    """Information about a git repository."""

    name: str
    path: Path
    url: Optional[str] = None
    branch: Optional[str] = None
    commit: Optional[str] = None
    author: Optional[str] = None
    message: Optional[str] = None
    dirty: bool = False
    ahead: int = 0
    behind: int = 0
    branches: list[str] = field(default_factory=list)
    remotes: list[str] = field(default_factory=list)


class GitManager:
    """Manages git repositories for Odoo instances."""

    def __init__(self, repos_dir: Optional[Path] = None):
        """Initialize the Git manager.

        Args:
            repos_dir: Directory to store repositories. Defaults to ~/odoo-manager/repos.
        """
        self.repos_dir = repos_dir or DEFAULT_GIT_REPOS_DIR
        self.repos_dir.mkdir(parents=True, exist_ok=True)

    def clone(
        self,
        url: str,
        name: Optional[str] = None,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
    ) -> GitRepoInfo:
        """Clone a git repository.

        Args:
            url: Git repository URL (https, ssh, or local path).
            name: Name for the repository. Defaults to repo name from URL.
            branch: Specific branch to clone. Defaults to default branch.
            depth: Clone depth. None for full clone.

        Returns:
            GitRepoInfo with repository information.

        Raises:
            GitError: If cloning fails.
        """
        # Determine repository name from URL
        if name is None:
            name = self._extract_repo_name(url)

        repo_path = self.repos_dir / name

        if repo_path.exists():
            raise GitError(f"Repository '{name}' already exists at {repo_path}")

        try:
            info(f"Cloning {url}...")
            if branch:
                repo = Repo.clone_from(url, repo_path, branch=branch, depth=depth)
            else:
                repo = Repo.clone_from(url, repo_path, depth=depth)

            success(f"Cloned repository '{name}' to {repo_path}")
            return self._get_repo_info(repo, name)

        except GitCommandError as e:
            raise GitError(f"Failed to clone repository: {e.stderr}") from e
        except Exception as e:
            raise GitError(f"Failed to clone repository: {e}") from e

    def get_repo(self, name: str) -> Repo:
        """Get a git repository by name.

        Args:
            name: Repository name.

        Returns:
            GitPython Repo object.

        Raises:
            GitError: If repository not found or invalid.
        """
        repo_path = self.repos_dir / name

        if not repo_path.exists():
            raise GitError(f"Repository '{name}' not found at {repo_path}")

        try:
            return Repo(repo_path)
        except InvalidGitRepositoryError as e:
            raise GitError(f"'{name}' is not a valid git repository") from e

    def list_repos(self) -> list[GitRepoInfo]:
        """List all managed repositories.

        Returns:
            List of GitRepoInfo objects.
        """
        repos = []

        for path in self.repos_dir.iterdir():
            if not path.is_dir():
                continue

            try:
                repo = Repo(path)
                info = self._get_repo_info(repo, path.name)
                repos.append(info)
            except InvalidGitRepositoryError:
                # Skip non-git directories
                continue

        return repos

    def get_branches(
        self, name: str, branch_type: GitBranchType = GitBranchType.LOCAL
    ) -> list[str]:
        """Get branches from a repository.

        Args:
            name: Repository name.
            branch_type: Type of branches to list.

        Returns:
            List of branch names.
        """
        repo = self.get_repo(name)

        if branch_type == GitBranchType.LOCAL:
            return [h.name for h in repo.heads]
        elif branch_type == GitBranchType.REMOTE:
            branches = []
            for remote in repo.remotes:
                branches.extend([r.name.split("/")[-1] for r in remote.refs])
            return branches
        else:  # ALL
            local = {h.name for h in repo.heads}
            remote = set()
            for r in repo.remotes:
                remote.update(ref.name.split("/")[-1] for ref in r.refs)
            return sorted(local | remote)

    def checkout(self, name: str, branch: str, create: bool = False) -> None:
        """Checkout a branch in a repository.

        Args:
            name: Repository name.
            branch: Branch name to checkout.
            create: Whether to create the branch if it doesn't exist.
        """
        repo = self.get_repo(name)

        try:
            if create:
                # Check if branch exists locally or remotely
                local_branches = [h.name for h in repo.heads]
                remote_branches = []

                for remote in repo.remotes:
                    remote_branches.extend(
                        [r.name.split("/")[-1] for r in remote.refs]
                    )

                if branch in local_branches:
                    repo.heads[branch].checkout()
                elif branch in remote_branches:
                    # Create local branch tracking remote
                    remote_ref = next(
                        r
                        for remote in repo.remotes
                        for r in remote.refs
                        if r.name.split("/")[-1] == branch
                    )
                    repo.create_head(branch, remote_ref).set_tracking_branch(
                        remote_ref
                    ).checkout()
                else:
                    # Create new branch from current HEAD
                    repo.create_head(branch).checkout()
                info(f"Created and checked out new branch '{branch}'")
            else:
                # Checkout existing branch
                repo.heads[branch].checkout()
                info(f"Checked out branch '{branch}'")

        except (IndexError, AttributeError) as e:
            raise GitError(f"Branch '{branch}' not found") from e

    def pull(self, name: str, remote: str = "origin", branch: Optional[str] = None) -> None:
        """Pull latest changes from remote.

        Args:
            name: Repository name.
            remote: Remote name. Defaults to "origin".
            branch: Branch to pull. Defaults to current branch.
        """
        repo = self.get_repo(name)

        if branch is None:
            branch = repo.active_branch.name

        try:
            info(f"Pulling {remote}/{branch}...")
            repo.remotes[remote].pull(branch)
            success(f"Pulled latest changes for '{branch}'")

        except GitCommandError as e:
            raise GitError(f"Failed to pull: {e.stderr}") from e

    def fetch(self, name: str, remote: str = "origin") -> None:
        """Fetch changes from remote without merging.

        Args:
            name: Repository name.
            remote: Remote name. Defaults to "origin".
        """
        repo = self.get_repo(name)

        try:
            info(f"Fetching from {remote}...")
            repo.remotes[remote].fetch()
            success(f"Fetched updates from {remote}")

        except GitCommandError as e:
            raise GitError(f"Failed to fetch: {e.stderr}") from e

    def get_status(self, name: str) -> GitRepoInfo:
        """Get detailed status of a repository.

        Args:
            name: Repository name.

        Returns:
            GitRepoInfo with current status.
        """
        repo = self.get_repo(name)
        return self._get_repo_info(repo, name)

    def add_remote(self, name: str, remote_name: str, url: str) -> None:
        """Add a remote to a repository.

        Args:
            name: Repository name.
            remote_name: Name for the remote.
            url: Remote URL.
        """
        repo = self.get_repo(name)

        try:
            repo.create_remote(remote_name, url)
            success(f"Added remote '{remote_name}' -> {url}")

        except GitCommandError as e:
            raise GitError(f"Failed to add remote: {e.stderr}") from e

    def remove_repo(self, name: str, keep_files: bool = False) -> None:
        """Remove a repository from management.

        Args:
            name: Repository name.
            keep_files: If True, keep files but remove from management.
        """
        repo_path = self.repos_dir / name

        if not repo_path.exists():
            raise GitError(f"Repository '{name}' not found")

        if not keep_files:
            import shutil

            shutil.rmtree(repo_path)
            info(f"Removed repository '{name}'")
        else:
            # Remove .git directory only
            git_dir = repo_path / ".git"
            if git_dir.exists():
                import shutil

                shutil.rmtree(git_dir)
                info(f"Removed git tracking from '{name}'")

    def get_repo_path(self, name: str) -> Path:
        """Get the filesystem path for a repository.

        Args:
            name: Repository name.

        Returns:
            Path to the repository.
        """
        path = self.repos_dir / name
        if not path.exists():
            raise GitError(f"Repository '{name}' not found")
        return path

    def _extract_repo_name(self, url: str) -> str:
        """Extract repository name from URL.

        Args:
            url: Git repository URL.

        Returns:
            Repository name.
        """
        # Remove trailing slash
        url = url.rstrip("/")

        # Extract name from URL
        # Handle: https://github.com/user/repo.git
        # Handle: https://github.com/user/repo
        # Handle: git@github.com:user/repo.git
        # Handle: /local/path/to/repo

        if ".git" in url:
            url = url[: -len(".git")]

        name = url.split("/")[-1]
        return name

    def _get_repo_info(self, repo: Repo, name: str) -> GitRepoInfo:
        """Extract information from a git repository.

        Args:
            repo: GitPython Repo object.
            name: Repository name.

        Returns:
            GitRepoInfo with repository details.
        """
        try:
            # Get current commit info
            commit = repo.head.commit
            current_branch = repo.active_branch.name

            # Get ahead/behind info
            ahead = 0
            behind = 0

            try:
                tracking_branch = repo.active_branch.tracking_branch()
                if tracking_branch:
                    ahead = sum(1 for _ in repo.iter_commits(f"HEAD..{tracking_branch.name}"))
                    behind = sum(1 for _ in repo.iter_commits(f"{tracking_branch.name}..HEAD"))
            except (ValueError, AttributeError):
                pass

            # Get remotes
            remotes = [r.name for r in repo.remotes]

            # Get origin URL if available
            url = None
            try:
                origin = repo.remotes.origin
                url = next(origin.urls, None)
            except (AttributeError, ValueError):
                pass

            return GitRepoInfo(
                name=name,
                path=Path(repo.working_dir),
                url=url,
                branch=current_branch,
                commit=commit.hexsha[:8],
                author=str(commit.author),
                message=commit.message.strip().split("\n")[0][:80],
                dirty=repo.is_dirty(),
                ahead=ahead,
                behind=behind,
                branches=[h.name for h in repo.heads],
                remotes=remotes,
            )

        except Exception as e:
            # Return minimal info if there's an error
            return GitRepoInfo(
                name=name,
                path=Path(repo.working_dir) if repo.working_dir else self.repos_dir / name,
            )


def is_git_repo(path: Path) -> bool:
    """Check if a directory is a git repository.

    Args:
        path: Directory path to check.

    Returns:
        True if directory is a git repository.
    """
    try:
        Repo(path)
        return True
    except (InvalidGitRepositoryError, ValueError):
        return False


def get_current_branch(path: Path) -> Optional[str]:
    """Get the current branch name of a git repository.

    Args:
        path: Path to the repository.

    Returns:
        Branch name or None if not a git repo.
    """
    try:
        repo = Repo(path)
        return repo.active_branch.name
    except (InvalidGitRepositoryError, ValueError):
        return None


def get_current_commit(path: Path) -> Optional[str]:
    """Get the current commit hash of a git repository.

    Args:
        path: Path to the repository.

    Returns:
        Commit hash (short) or None if not a git repo.
    """
    try:
        repo = Repo(path)
        return repo.head.commit.hexsha[:8]
    except (InvalidGitRepositoryError, ValueError):
        return None
