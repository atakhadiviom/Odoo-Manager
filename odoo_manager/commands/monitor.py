"""
Monitor commands for Odoo Manager CLI.
"""

from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table

from odoo_manager.core.monitor import (
    HealthMonitor,
    HealthStatus,
    AutoRestart,
)
from odoo_manager.core.instance import InstanceManager
from odoo_manager.utils.output import console, success, error, info, warn


@click.group(name="monitor")
def monitor_cli():
    """Monitor instance health and status."""
    pass


@monitor_cli.command(name="status")
@click.option("--instance", "-i", help="Specific instance to check")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed check results")
@click.pass_context
def monitor_status(ctx, instance, verbose):
    """Show health status of instances.

    Example: odoo-manager monitor status --instance production
    """
    try:
        monitor = HealthMonitor()

        if instance:
            manager = InstanceManager()
            inst = manager.get_instance(instance)
            health = monitor.check_instance(inst)
            _print_health_summary(health, verbose)
        else:
            healths = monitor.check_all_instances()
            _print_health_table(healths)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@monitor_cli.command(name="check")
@click.argument("instance")
@click.pass_context
def monitor_check(ctx, instance):
    """Run health check on an instance.

    Example: odoo-manager monitor check production
    """
    try:
        monitor = HealthMonitor()
        manager = InstanceManager()
        inst = manager.get_instance(instance)
        health = monitor.check_instance(inst)

        _print_health_details(health)

        # Exit with error code if critical
        if health.status == HealthStatus.CRITICAL:
            error(f"Instance '{instance}' is in CRITICAL state")
            ctx.exit(2)
        elif health.status == HealthStatus.WARNING:
            warn(f"Instance '{instance}' has WARNINGs")
            ctx.exit(1)
        else:
            success(f"Instance '{instance}' is HEALTHY")

    except Exception as e:
        error(str(e))
        ctx.exit(2)


@monitor_cli.command(name="logs")
@click.argument("instance")
@click.option("--tail", "-n", type=int, default=50, help="Number of recent errors to show")
@click.pass_context
def monitor_logs(ctx, instance, tail):
    """Show recent errors from instance logs.

    Example: odoo-manager monitor logs production --tail 100
    """
    try:
        manager = InstanceManager()
        inst = manager.get_instance(instance)
        logs = inst.get_logs(follow=False, tail=500)

        # Filter for errors and warnings
        error_lines = []
        for line in logs.split("\n"):
            line_lower = line.lower()
            if "error" in line_lower or "critical" in line_lower or "exception" in line_lower:
                error_lines.append(line)

        if not error_lines:
            info("No errors found in recent logs")
            return

        console.print(Panel(f"[bold red]Recent Errors[/bold red] ({len(error_lines)} total)"))

        for line in error_lines[-tail:]:
            console.print(line.rstrip())

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@monitor_cli.command(name="top")
@click.option("--refresh", "-r", type=int, default=5, help="Refresh interval in seconds")
@click.pass_context
def monitor_top(ctx, refresh):
    """Show live resource usage.

    Example: odoo-manager monitor top --refresh 2
    """
    try:
        import time

        monitor = HealthMonitor()

        while True:
            console.clear()
            healths = monitor.check_all_instances()

            table = Table(title=f"Resource Usage - Refreshing every {refresh}s")
            table.add_column("Instance", style="cyan")
            table.add_column("Status", style="bold")
            table.add_column("CPU %")
            table.add_column("Memory %")
            table.add_column("Memory MB")
            table.add_column("Disk %")

            for health in healths:
                status_color = {
                    HealthStatus.HEALTHY: "green",
                    HealthStatus.WARNING: "yellow",
                    HealthStatus.CRITICAL: "red",
                    HealthStatus.UNKNOWN: "dim",
                }.get(health.status, "white")

                # Colorize values
                cpu_val = health.cpu_percent
                cpu_str = f"{cpu_val:.1f}"
                if cpu_val >= 90:
                    cpu_str = f"[red]{cpu_str}[/red]"
                elif cpu_val >= 70:
                    cpu_str = f"[yellow]{cpu_str}[/yellow]"

                mem_val = health.memory_percent
                mem_str = f"{mem_val:.1f}"
                if mem_val >= 85:
                    mem_str = f"[red]{mem_str}[/red]"
                elif mem_val >= 70:
                    mem_str = f"[yellow]{mem_str}[/yellow]"

                disk_val = health.disk_percent
                disk_str = f"{disk_val:.1f}"
                if disk_val >= 90:
                    disk_str = f"[red]{disk_str}[/red]"
                elif disk_val >= 80:
                    disk_str = f"[yellow]{disk_str}[/yellow]"

                table.add_row(
                    health.instance_name,
                    f"[{status_color}]{health.status}[/{status_color}]",
                    cpu_str,
                    mem_str,
                    str(health.memory_mb),
                    disk_str,
                )

            console.print(table)
            console.print(f"\n[dim]Press Ctrl+C to exit[/dim]")

            try:
                time.sleep(refresh)
            except KeyboardInterrupt:
                console.print("\n[yellow]Monitoring stopped[/yellow]")
                break

    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped[/yellow]")
    except Exception as e:
        error(str(e))
        ctx.exit(1)


@monitor_cli.command(name="auto-restart")
@click.argument("instance")
@click.option("--max", type=int, default=3, help="Maximum restarts")
@click.option("--window", type=int, default=300, help="Time window in seconds")
@click.option("--dry-run", is_flag=True, help="Check without restarting")
@click.pass_context
def monitor_auto_restart(ctx, instance, max, window, dry_run):
    """Configure or trigger auto-restart for an instance.

    Example: odoo-manager monitor auto-restart production --max 5
    """
    try:
        manager = InstanceManager()
        inst = manager.get_instance(instance)

        if inst.is_running():
            info(f"Instance '{instance}' is running - no action needed")
            return

        auto_restart = AutoRestart(max_restarts=max, restart_window=window)

        if auto_restart.should_restart(instance):
            if dry_run:
                info(f"Would restart '{instance}' (dry run)")
                info(f"Restart count: {auto_restart.get_restart_count(instance)}/{max}")
            else:
                info(f"Auto-restarting '{instance}'...")
                inst.start()
                auto_restart.record_restart(instance)
                success(f"Instance '{instance}' restarted")
        else:
            warn(f"Auto-restart limit reached for '{instance}'")
            warn(f"Restarted {auto_restart.get_restart_count(instance)} times in last {window}s")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


def _print_health_table(healths):
    """Print health status table."""
    table = Table(title="Instance Health Status")
    table.add_column("Instance", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("CPU %")
    table.add_column("Memory %")
    table.add_column("Disk %")
    table.add_column("Last Check")

    for health in healths:
        status_color = {
            HealthStatus.HEALTHY: "green",
            HealthStatus.WARNING: "yellow",
            HealthStatus.CRITICAL: "red",
            HealthStatus.UNKNOWN: "dim",
        }.get(health.status, "white")

        table.add_row(
            health.instance_name,
            f"[{status_color}]{health.status}[/{status_color}]",
            f"{health.cpu_percent:.1f}",
            f"{health.memory_percent:.1f}",
            f"{health.disk_percent:.1f}",
            health.last_check.strftime("%H:%M:%S"),
        )

    console.print(table)


def _print_health_summary(health, verbose):
    """Print health summary for one instance."""
    status_color = {
        HealthStatus.HEALTHY: "green",
        HealthStatus.WARNING: "yellow",
        HealthStatus.CRITICAL: "red",
        HealthStatus.UNKNOWN: "dim",
    }.get(health.status, "white")

    console.print(f"[bold]{health.instance_name}[/bold]")
    console.print(f"Status: [{status_color}]{health.status}[/{status_color}]")
    console.print(f"CPU: {health.cpu_percent:.1f}%")
    console.print(f"Memory: {health.memory_mb}MB ({health.memory_percent:.1f}%)")
    console.print(f"Disk: {health.disk_percent:.1f}%")
    console.print(f"Last check: {health.last_check.strftime('%Y-%m-%d %H:%M:%S')}")

    if verbose:
        console.print("\nChecks:")
        for check in health.checks:
            check_color = {
                HealthStatus.HEALTHY: "green",
                HealthStatus.WARNING: "yellow",
                HealthStatus.CRITICAL: "red",
                HealthStatus.UNKNOWN: "dim",
            }.get(check.status, "white")

            console.print(
                f"  [{check_color}]✓[{check_color}] {check.name}: {check.message}"
            )


def _print_health_details(health):
    """Print detailed health information."""
    console.print()
    console.print(f"[bold]Health Check: {health.instance_name}[/bold]")
    console.print("=" * 50)

    status_color = {
        HealthStatus.HEALTHY: "green",
        HealthStatus.WARNING: "yellow",
        HealthStatus.CRITICAL: "red",
        HealthStatus.UNKNOWN: "dim",
    }.get(health.status, "white")

    console.print(f"Overall Status: [{status_color}]{health.status.upper()}[/{status_color}]")
    console.print(f"Last Check: {health.last_check.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print()

    # Resource usage
    console.print("[bold]Resource Usage:[/bold]")
    console.print(f"  CPU: {health.cpu_percent:.1f}%")
    console.print(f"  Memory: {health.memory_mb}MB ({health.memory_percent:.1f}%)")
    console.print(f"  Disk: {health.disk_percent:.1f}%")
    console.print()

    # Individual checks
    console.print("[bold]Checks:[/bold]")
    for check in health.checks:
        check_color = {
            HealthStatus.HEALTHY: "green",
            HealthStatus.WARNING: "yellow",
            HealthStatus.CRITICAL: "red",
            HealthStatus.UNKNOWN: "dim",
        }.get(check.status, "white")

        status_symbol = {
            HealthStatus.HEALTHY: "✓",
            HealthStatus.WARNING: "⚠",
            HealthStatus.CRITICAL: "✗",
            HealthStatus.UNKNOWN: "?",
        }.get(check.status, "?")

        console.print(
            f"  [{check_color}]{status_symbol}[/{check_color}] {check.name}: {check.message}"
        )

        if check.value and isinstance(check.value, dict):
            for key, value in check.value.items():
                console.print(f"      {key}: {value}")
