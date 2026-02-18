"""
Deployment commands for Odoo Manager CLI.
"""

from pathlib import Path

import click
from rich.table import Table

from odoo_manager.core.cicd import (
    CICDPipeline,
    PipelineResult,
    save_pipeline_result,
    ValidationStatus,
)
from odoo_manager.core.environment import EnvironmentManager
from odoo_manager.utils.output import console, success, error, info, warn


@click.group(name="deploy")
def deploy_cli():
    """Deploy and manage CI/CD pipelines."""
    pass


@deploy_cli.command(name="validate")
@click.option("--branch", "-b", required=True, help="Git branch to validate")
@click.option("--repo", "-r", required=True, help="Git repository name")
@click.option("--environment", "-e", required=True, help="Target environment")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed results")
@click.pass_context
def deploy_validate(ctx, branch, repo, environment, verbose):
    """Run validation without deploying.

    Example: odoo-manager deploy validate --branch main --repo odoo --environment production
    """
    try:
        pipeline = CICDPipeline()
        result = pipeline.validate_deployment(branch, repo, environment)

        # Save result
        save_pipeline_result(result, pipeline.config_path or Path.home() / ".config" / "odoo-manager")

        # Print results
        _print_validation_results(result, verbose)

        # Exit with error code if failed
        if result.status == ValidationStatus.FAILED:
            ctx.exit(1)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@deploy_cli.command(name="run")
@click.option("--branch", "-b", required=True, help="Git branch to deploy")
@click.option("--environment", "-e", required=True, help="Target environment")
@click.option("--repo", "-r", help="Git repository name")
@click.option("--skip-validation", is_flag=True, help="Skip pre-deployment validation")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.pass_context
def deploy_run(ctx, branch, environment, repo, skip_validation, verbose):
    """Deploy a branch to an environment.

    Example: odoo-manager deploy run --branch main --environment production
    """
    try:
        pipeline = CICDPipeline()
        result = pipeline.deploy(
            branch=branch,
            environment=environment,
            repo=repo,
            skip_validation=skip_validation,
        )

        # Save result
        save_pipeline_result(result, pipeline.config_path or Path.home() / ".config" / "odoo-manager")

        # Print results
        _print_deployment_results(result, verbose)

        # Exit with error code if failed
        if result.status == ValidationStatus.FAILED:
            ctx.exit(1)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@deploy_cli.command(name="rollback")
@click.argument("environment")
@click.option("--target", "-t", help="Specific deployment ID to rollback to")
@click.pass_context
def deploy_rollback(ctx, environment, target):
    """Rollback an environment to a previous deployment.

    Example: odoo-manager deploy rollback production --target abc123
    """
    try:
        pipeline = CICDPipeline()

        info(f"Rolling back '{environment}'...")

        deployment = pipeline.rollback(environment, target_id=target)

        success(f"Rollback completed: {deployment.branch} @ {deployment.commit}")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@deploy_cli.command(name="history")
@click.argument("environment")
@click.option("--limit", "-l", type=int, default=20, help="Number of records to show")
@click.pass_context
def deploy_history(ctx, environment, limit):
    """Show deployment pipeline history.

    Example: odoo-manager deploy history production --limit 50
    """
    try:
        env_mgr = EnvironmentManager()
        pipeline_history = env_mgr.get_deployment_history(environment, limit=limit)

        if not pipeline_history:
            info(f"No deployment history found for '{environment}'.")
            return

        table = Table(title=f"Deployment History - {environment}")
        table.add_column("ID", style="dim")
        table.add_column("Branch", style="cyan")
        table.add_column("Commit", style="yellow")
        table.add_column("Author")
        table.add_column("Time")
        table.add_column("Status", style="bold")

        for record in pipeline_history:
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


@deploy_cli.command(name="status")
@click.argument("pipeline_id")
@click.pass_context
def deploy_status(ctx, pipeline_id):
    """Show status of a pipeline run.

    Example: odoo-manager deploy status validate-production-20240115120000
    """
    try:
        config_dir = Path.home() / ".config" / "odoo-manager"
        results_file = config_dir / "pipeline_results.yaml"

        if not results_file.exists():
            info("No pipeline history found.")
            return

        import yaml

        with open(results_file, "r") as f:
            data = yaml.safe_load(f) or []

        for record in reversed(data):
            if record.get("id", "").startswith(pipeline_id):
                _print_pipeline_status(record)
                return

        error(f"Pipeline '{pipeline_id}' not found")
        ctx.exit(1)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@deploy_cli.command(name="list")
@click.option("--environment", "-e", help="Filter by environment")
@click.option("--limit", "-l", type=int, default=20, help="Number of records to show")
@click.pass_context
def deploy_list(ctx, environment, limit):
    """List recent pipeline runs.

    Example: odoo-manager deploy list --environment production
    """
    try:
        config_dir = Path.home() / ".config" / "odoo-manager"
        results_file = config_dir / "pipeline_results.yaml"

        if not results_file.exists():
            info("No pipeline history found.")
            return

        import yaml
        from datetime import datetime

        with open(results_file, "r") as f:
            data = yaml.safe_load(f) or []

        # Filter by environment
        if environment:
            data = [d for d in data if d.get("environment") == environment]

        # Sort by started_at descending
        data.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        data = data[:limit]

        if not data:
            info("No pipeline runs found.")
            return

        table = Table(title="Pipeline Runs")
        table.add_column("ID", style="dim")
        table.add_column("Environment", style="cyan")
        table.add_column("Branch", style="green")
        table.add_column("Status", style="bold")
        table.add_column("Started")

        for record in data:
            status = record.get("status", "unknown")
            status_style = {
                "passed": "green",
                "failed": "red",
                "running": "yellow",
            }.get(status, "dim")

            started = record.get("started_at", "")
            if started:
                try:
                    started_dt = datetime.fromisoformat(started)
                    started = started_dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass

            table.add_row(
                record.get("id", "")[:12],
                record.get("environment", ""),
                record.get("branch", ""),
                f"[{status_style}]{status}[/{status_style}]",
                started,
            )

        console.print(table)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


def _print_validation_results(result: PipelineResult, verbose: bool = False) -> None:
    """Print validation results."""
    console.print()
    console.print(f"[bold]Validation Results[/bold]")
    console.print(f"Environment: [cyan]{result.environment}[/cyan]")
    console.print(f"Branch: [cyan]{result.branch}[/cyan]")
    console.print(f"Commit: {result.commit}")
    console.print()

    table = Table()
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Duration")
    table.add_column("Message")

    for validation in result.validations:
        status_color = {
            ValidationStatus.PASSED: "green",
            ValidationStatus.FAILED: "red",
            ValidationStatus.SKIPPED: "dim",
            ValidationStatus.RUNNING: "yellow",
        }.get(validation.status, "white")

        table.add_row(
            validation.name,
            f"[{status_color}]{validation.status}[/{status_color}]",
            f"{validation.duration:.2f}s",
            validation.message,
        )

        if verbose and validation.details:
            for key, value in validation.details.items():
                if isinstance(value, list):
                    for item in value[:3]:
                        console.print(f"  [dim]  {key}: {item}[/dim]")
                else:
                    console.print(f"  [dim]  {key}: {value}[/dim]")

    console.print(table)

    # Overall status
    if result.status == ValidationStatus.PASSED:
        console.print("[green]✓ All validations passed[/green]")
    else:
        console.print("[red]✗ Validation failed[/red]")


def _print_deployment_results(result: PipelineResult, verbose: bool = False) -> None:
    """Print deployment results."""
    console.print()
    console.print(f"[bold]Deployment Results[/bold]")
    console.print(f"Environment: [cyan]{result.environment}[/cyan]")
    console.print(f"Branch: [cyan]{result.branch}[/cyan]")
    console.print(f"Commit: {result.commit}")
    console.print()

    # Print validation summary
    if result.validations:
        passed = sum(1 for v in result.validations if v.status == ValidationStatus.PASSED)
        failed = sum(1 for v in result.validations if v.status == ValidationStatus.FAILED)
        console.print(f"Validations: [green]{passed} passed[/green], [red]{failed} failed[/red]")

    # Overall status
    status_color = "green" if result.status == ValidationStatus.PASSED else "red"
    console.print(f"Status: [{status_color}]{result.status}[/{status_color}]")

    if result.error_message:
        console.print(f"Error: {result.error_message}")

    if result.deployment:
        console.print(f"Deployed at: {result.deployment.timestamp}")

    if result.rollback_deployment:
        console.print(f"[yellow]Rolled back to: {result.rollback_deployment.branch} @ {result.rollback_deployment.commit}[/yellow]")


def _print_pipeline_status(record: dict) -> None:
    """Print pipeline status from record."""
    console.print(f"[bold]Pipeline: {record.get('id', '')}[/bold]")
    console.print(f"Environment: {record.get('environment', '')}")
    console.print(f"Branch: {record.get('branch', '')}")
    console.print(f"Commit: {record.get('commit', '')}")

    status = record.get("status", "unknown")
    status_color = {"passed": "green", "failed": "red", "running": "yellow"}.get(status, "white")
    console.print(f"Status: [{status_color}]{status}[/{status_color}]")

    if record.get("error_message"):
        console.print(f"Error: {record['error_message']}")

    if record.get("started_at"):
        console.print(f"Started: {record['started_at']}")

    if record.get("completed_at"):
        console.print(f"Completed: {record['completed_at']}")
