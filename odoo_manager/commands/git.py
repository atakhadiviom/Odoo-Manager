"""
Git commands for Odoo Manager CLI.
"""

from pathlib import Path

import click
from rich.table import Table

from odoo_manager.core.git import GitManager, GitBranchType, GitRepoInfo
from odoo_manager.exceptions import GitError
from odoo_manager.utils.output import console, success, error, info, warn


@click.group(name="git")
def git_cli():
    """Manage git repositories for Odoo deployments."""
    pass


@git_cli.command(name="clone")
@click.argument("url")
@click.option(
    "--name", "-n", help="Repository name (defaults to repo name from URL)"
)
@click.option("--branch", "-b", help="Specific branch to clone")
@click.option(
    "--depth", "-d", type=int, help="Clone depth (shallow clone)"
)
@click.pass_context
def git_clone(ctx, url, name, branch, depth):
    """Clone a git repository.

    Example: odoo-manager git clone https://github.com/odoo/odoo.git
    """
    try:
        git_mgr = GitManager()
        repo_info = git_mgr.clone(url, name=name, branch=branch, depth=depth)

        console.print(f"[green]✓[/green] Repository cloned successfully!")
        console.print(f"  Name: [cyan]{repo_info.name}[/cyan]")
        console.print(f"  Path: {repo_info.path}")
        console.print(f"  Branch: [cyan]{repo_info.branch}[/cyan]")
        if repo_info.commit:
            console.print(f"  Commit: {repo_info.commit}")

    except GitError as e:
        error(str(e))
        ctx.exit(1)


@git_cli.command(name="ls")
@click.option(
    "--verbose", "-v", is_flag=True, help="Show detailed information"
)
@click.pass_context
def git_list(ctx, verbose):
    """List all git repositories.

    Example: odoo-manager git ls
    """
    try:
        git_mgr = GitManager()
        repos = git_mgr.list_repos()

        if not repos:
            info("No repositories found.")
            return

        if verbose:
            for repo in repos:
                _print_repo_info(repo)
                console.print()
        else:
            table = Table(title="Git Repositories")
            table.add_column("Name", style="cyan")
            table.add_column("Branch", style="green")
            table.add_column("Commit", style="yellow")
            table.add_column("Status", style="bold")

            for repo in repos:
                status = ""
                if repo.dirty:
                    status += "[red]✗ dirty[/red] "
                if repo.ahead > 0:
                    status += "[yellow]↑{}[/yellow] ".format(repo.ahead)
                if repo.behind > 0:
                    status += "[blue]↓{}[/blue] ".format(repo.behind)
                if not status:
                    status = "[green]✓ clean[/green]"

                table.add_row(
                    repo.name,
                    repo.branch or "-",
                    repo.commit or "-",
                    status,
                )

            console.print(table)

    except GitError as e:
        error(str(e))
        ctx.exit(1)


@git_cli.command(name="branches")
@click.argument("name")
@click.option(
    "--type",
    "-t",
    type=click.Choice(["local", "remote", "all"]),
    default="local",
    help="Branch type to list",
)
@click.pass_context
def git_branches(ctx, name, type):
    """List branches in a repository.

    Example: odoo-manager git branches odoo --type=all
    """
    try:
        git_mgr = GitManager()
        branch_type = GitBranchType(type)

        branches = git_mgr.get_branches(name, branch_type)

        if not branches:
            info(f"No branches found for '{name}'.")
            return

        table = Table(title=f"Branches - {name}")
        table.add_column("Branch", style="cyan")

        # Mark current branch
        repo_info = git_mgr.get_status(name)
        current = repo_info.branch

        for branch in sorted(branches):
            marker = " [green]*[/green]" if branch == current else ""
            table.add_row(branch + marker)

        console.print(table)

    except GitError as e:
        error(str(e))
        ctx.exit(1)


@git_cli.command(name="checkout")
@click.argument("name")
@click.argument("branch")
@click.option(
    "--create", "-c", is_flag=True, help="Create branch if it doesn't exist"
)
@click.pass_context
def git_checkout(ctx, name, branch, create):
    """Checkout a branch in a repository.

    Example: odoo-manager git checkout odoo 17.0
    """
    try:
        git_mgr = GitManager()
        git_mgr.checkout(name, branch, create=create)
        success(f"Checked out branch '{branch}' in '{name}'")

    except GitError as e:
        error(str(e))
        ctx.exit(1)


@git_cli.command(name="pull")
@click.argument("name")
@click.option("--remote", "-r", default="origin", help="Remote name")
@click.option("--branch", "-b", help="Branch to pull (defaults to current)")
@click.pass_context
def git_pull(ctx, name, remote, branch):
    """Pull latest changes from remote.

    Example: odoo-manager git pull odoo --remote upstream
    """
    try:
        git_mgr = GitManager()
        git_mgr.pull(name, remote=remote, branch=branch)
        success(f"Pulled latest changes for '{name}'")

    except GitError as e:
        error(str(e))
        ctx.exit(1)


@git_cli.command(name="fetch")
@click.argument("name")
@click.option("--remote", "-r", default="origin", help="Remote name")
@click.pass_context
def git_fetch(ctx, name, remote):
    """Fetch changes from remote without merging.

    Example: odoo-manager git fetch odoo
    """
    try:
        git_mgr = GitManager()
        git_mgr.fetch(name, remote=remote)
        success(f"Fetched updates from {remote}")

    except GitError as e:
        error(str(e))
        ctx.exit(1)


@git_cli.command(name="status")
@click.argument("name")
@click.pass_context
def git_status(ctx, name):
    """Show detailed status of a repository.

    Example: odoo-manager git status odoo
    """
    try:
        git_mgr = GitManager()
        repo_info = git_mgr.get_status(name)
        _print_repo_info(repo_info)

    except GitError as e:
        error(str(e))
        ctx.exit(1)


@git_cli.command(name="rm")
@click.argument("name")
@click.option(
    "--keep-files", is_flag=True, help="Keep files, remove git tracking only"
)
@click.confirmation_option(prompt="Are you sure you want to remove this repository?")
@click.pass_context
def git_remove(ctx, name, keep_files):
    """Remove a repository.

    Example: odoo-manager git rm old-repo
    """
    try:
        git_mgr = GitManager()
        git_mgr.remove_repo(name, keep_files=keep_files)
        success(f"Repository '{name}' removed")

    except GitError as e:
        error(str(e))
        ctx.exit(1)


@git_cli.command(name="path")
@click.argument("name")
@click.pass_context
def git_path(ctx, name):
    """Get the filesystem path for a repository.

    Example: odoo-manager git path odoo
    """
    try:
        git_mgr = GitManager()
        path = git_mgr.get_repo_path(name)
        console.print(str(path))

    except GitError as e:
        error(str(e))
        ctx.exit(1)


@git_cli.command(name="remote")
@click.argument("name")
@click.argument("remote_name")
@click.argument("url")
@click.pass_context
def git_remote_add(ctx, name, remote_name, url):
    """Add a remote to a repository.

    Example: odoo-manager git remote odoo upstream https://github.com/odoo/odoo.git
    """
    try:
        git_mgr = GitManager()
        git_mgr.add_remote(name, remote_name, url)
        success(f"Added remote '{remote_name}' to '{name}'")

    except GitError as e:
        error(str(e))
        ctx.exit(1)


def _print_repo_info(repo: GitRepoInfo) -> None:
    """Print detailed repository information."""
    console.print(f"[bold cyan]{repo.name}[/bold cyan]")
    console.print(f"  Path: {repo.path}")

    if repo.url:
        console.print(f"  URL: {repo.url}")

    console.print(f"  Branch: [green]{repo.branch or 'N/A'}[/green]")

    if repo.commit:
        console.print(f"  Commit: [yellow]{repo.commit}[/yellow]")

    if repo.author:
        console.print(f"  Author: {repo.author}")

    if repo.message:
        console.print(f"  Message: {repo.message}")

    # Status indicators
    status_items = []
    if repo.dirty:
        status_items.append("[red]dirty[/red]")
    if repo.ahead > 0:
        status_items.append(f"[yellow]↑{repo.ahead}[/yellow]")
    if repo.behind > 0:
        status_items.append(f"[blue]↓{repo.behind}[/blue]")

    if status_items:
        console.print(f"  Status: {' '.join(status_items)}")

    # Branches
    if repo.branches:
        console.print(f"  Branches ({len(repo.branches)}): [cyan]{', '.join(sorted(repo.branches[:10]))}[/cyan]")
        if len(repo.branches) > 10:
            console.print(f"    ... and {len(repo.branches) - 10} more")

    # Remotes
    if repo.remotes:
        console.print(f"  Remotes: [cyan]{', '.join(repo.remotes)}[/cyan]")
