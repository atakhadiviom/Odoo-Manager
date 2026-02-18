"""
Environment commands for Odoo Manager CLI.
"""

from pathlib import Path

import click
from rich.table import Table

from odoo_manager.core.environment import EnvironmentManager, EnvironmentStatus
from odoo_manager.exceptions import EnvironmentNotFoundError
from odoo_manager.utils.output import console, success, error, info


@click.group(name="env")
def env_cli():
    """Manage deployment environments."""
    pass


@env_cli.command(name="ls")
@click.option("--tier", "-t", help="Filter by tier (dev, staging, production)")
@click.pass_context
def env_list(ctx, tier):
    """List all environments.

    Example: odoo-manager env ls --tier dev
    """
    try:
        env_mgr = EnvironmentManager()
        environments = env_mgr.list_environments(tier=tier)

        if not environments:
            info("No environments found.")
            return

        table = Table(title="Environments")
        table.add_column("Name", style="cyan")
        table.add_column("Tier", style="green")
        table.add_column("Workers", style="yellow")
        table.add_column("Port", style="blue")
        table.add_column("Auto-Deploy", style="dim")

        for env in environments:
            auto_deploy = ", ".join(env.auto_deploy_branches[:3])
            if len(env.auto_deploy_branches) > 3:
                auto_deploy += "..."

            table.add_row(
                env.name,
                env.tier,
                str(env.workers),
                str(env.port),
                auto_deploy or "-",
            )

        console.print(table)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@env_cli.command(name="create")
@click.argument("name")
@click.option(
    "--tier",
    "-t",
    type=click.Choice(["dev", "staging", "production"]),
    default="dev",
    help="Environment tier",
)
@click.option("--workers", "-w", type=int, default=4, help="Number of workers")
@click.option("--port", "-p", type=int, default=8069, help="Odoo port")
@click.option("--git-repo", "-r", help="Git repository name")
@click.option(
    "--auto-deploy",
    "-a",
    multiple=True,
    help="Auto-deploy branch pattern (can be used multiple times)",
)
@click.pass_context
def env_create(ctx, name, tier, workers, port, git_repo, auto_deploy):
    """Create a new environment.

    Example: odoo-manager env create staging --tier staging --port 8070
    """
    try:
        env_mgr = EnvironmentManager()

        env_mgr.create_environment(
            name=name,
            tier=tier,
            workers=workers,
            port=port,
            git_repo=git_repo,
            auto_deploy_branches=list(auto_deploy),
        )

        success(f"Environment '{name}' created successfully")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@env_cli.command(name="rm")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to remove this environment?")
@click.pass_context
def env_remove(ctx, name):
    """Remove an environment.

    Example: odoo-manager env rm old-env
    """
    try:
        env_mgr = EnvironmentManager()
        env_mgr.remove_environment(name)
        success(f"Environment '{name}' removed")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@env_cli.command(name="status")
@click.argument("name")
@click.pass_context
def env_status(ctx, name):
    """Show detailed status of an environment.

    Example: odoo-manager env status production
    """
    try:
        env_mgr = EnvironmentManager()
        status = env_mgr.get_status(name)

        console.print(f"[bold cyan]{status.name}[/bold cyan]")
        console.print(f"  Tier: [green]{status.tier}[/green]")

        if status.instance_name:
            instance_status = (
                "[green]running[/green]" if status.instance_status == "running" else f"[red]{status.instance_status}[/red]"
            )
            console.print(f"  Instance: {status.instance_name} ({instance_status})")
        else:
            console.print(f"  Instance: [dim]not configured[/dim]")

        if status.git_branch:
            dirty_marker = " [red]✗[/red]" if status.git_dirty else ""
            console.print(
                f"  Branch: [cyan]{status.git_branch}[/cyan] @ {status.git_commit}{dirty_marker}"
            )

        if status.last_deployment:
            console.print(f"  Last Deployment:")
            console.print(f"    Branch: {status.last_deployment.branch}")
            console.print(f"    Commit: {status.last_deployment.commit}")
            console.print(f"    Author: {status.last_deployment.author}")
            console.print(f"    Time: {status.last_deployment.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        if status.can_promote_to:
            console.print(f"  Can promote to: [cyan]{status.can_promote_to}[/cyan]")

    except EnvironmentNotFoundError as e:
        error(str(e))
        ctx.exit(1)
    except Exception as e:
        error(str(e))
        ctx.exit(1)


@env_cli.command(name="deploy")
@click.argument("branch")
@click.option("--environment", "-e", required=True, help="Target environment")
@click.option("--repo", "-r", help="Git repository name")
@click.option("--no-start", is_flag=True, help="Do not start instance after deployment")
@click.pass_context
def env_deploy(ctx, branch, environment, repo, no_start):
    """Deploy a branch to an environment.

    Example: odoo-manager env deploy main --environment production
    """
    try:
        env_mgr = EnvironmentManager()

        env_mgr.deploy(
            environment=environment,
            branch=branch,
            repo=repo,
            auto_start=not no_start,
        )

        success(f"Deployment to '{environment}' completed")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@env_cli.command(name="promote")
@click.argument("source")
@click.option("--target", "-t", help="Target environment (auto-detect if not specified)")
@click.pass_context
def env_promote(ctx, source, target):
    """Promote from one environment to the next tier.

    Example: odoo-manager env promote staging --target production
    """
    try:
        env_mgr = EnvironmentManager()

        env_mgr.promote(source_env=source, target_env=target)

        success(f"Promotion from '{source}' completed")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@env_cli.command(name="history")
@click.argument("name")
@click.option("--limit", "-l", type=int, default=10, help="Number of records to show")
@click.pass_context
def env_history(ctx, name, limit):
    """Show deployment history for an environment.

    Example: odoo-manager env history production --limit 20
    """
    try:
        env_mgr = EnvironmentManager()
        history = env_mgr.get_deployment_history(name, limit=limit)

        if not history:
            info(f"No deployment history found for '{name}'.")
            return

        table = Table(title=f"Deployment History - {name}")
        table.add_column("ID", style="dim")
        table.add_column("Branch", style="cyan")
        table.add_column("Commit", style="yellow")
        table.add_column("Author")
        table.add_column("Time")
        table.add_column("Status", style="bold")

        for record in history:
            status_style = "green" if record.status == "success" else "red"
            table.add_row(
                record.id[:8],
                record.branch,
                record.commit,
                record.author,
                record.timestamp.strftime("%Y-%m-%d %H:%M"),
                f"[{status_style}]{record.status}[/{status_style}]",
            )

        console.print(table)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@env_cli.command(name="auto-deploy")
@click.argument("environment")
@click.argument("branch")
@click.pass_context
def env_auto_deploy(ctx, environment, branch):
    """Check if a branch should be auto-deployed.

    Example: odoo-manager env auto-deploy dev feature/new-thing
    """
    try:
        env_mgr = EnvironmentManager()

        if env_mgr.should_auto_deploy(environment, branch):
            success(f"Branch '{branch}' matches auto-deploy rules for '{environment}'")
        else:
            info(f"Branch '{branch}' does not match auto-deploy rules for '{environment}'")

    except Exception as e:
        error(str(e))
        ctx.exit(1)
