"""
Scheduler commands for Odoo Manager CLI.
"""

from pathlib import Path

import click

from odoo_manager.core.scheduler import SchedulerManager, create_backup_task, create_health_check_task
from odoo_manager.core.backup import BackupManager
from odoo_manager.core.monitor import HealthMonitor
from odoo_manager.core.instance import InstanceManager
from odoo_manager.utils.output import console, success, error, info, warn


@click.group(name="scheduler")
def scheduler_cli():
    """Manage scheduled tasks."""
    pass


@scheduler_cli.command(name="start")
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground (daemon mode)")
@click.pass_context
def scheduler_start(ctx, foreground):
    """Start the scheduler daemon.

    Example: odoo-manager scheduler start
    """
    try:
        scheduler = SchedulerManager()

        if scheduler.is_running():
            warn("Scheduler is already running")
            return

        if foreground:
            info("Starting scheduler in foreground...")
            scheduler.start()

            # Keep running
            import time

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                scheduler.stop()
        else:
            # Start as daemon
            info("Starting scheduler daemon...")

            # Fork to background
            import os

            pid = os.fork()
            if pid > 0:
                # Parent process
                info(f"Scheduler started with PID {pid}")
                return

            # Child process
            os.setsid()
            scheduler.start()

            # Keep running
            import time

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                scheduler.stop()

        success("Scheduler started")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@scheduler_cli.command(name="stop")
@click.pass_context
def scheduler_stop(ctx):
    """Stop the scheduler daemon.

    Example: odoo-manager scheduler stop
    """
    try:
        scheduler = SchedulerManager()

        if not scheduler.is_running():
            warn("Scheduler is not running")
            return

        scheduler.stop()
        success("Scheduler stopped")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@scheduler_cli.command(name="status")
@click.pass_context
def scheduler_status(ctx):
    """Show scheduler status.

    Example: odoo-manager scheduler status
    """
    try:
        scheduler = SchedulerManager()

        if scheduler.is_running():
            success("Scheduler is running")

            tasks = scheduler.list_tasks()
            if tasks:
                console.print("\n[bold]Scheduled Tasks:[/bold]")
                from rich.table import Table

                table = Table()
                table.add_column("ID", style="cyan")
                table.add_column("Name")
                table.add_column("Next Run")
                table.add_column("Schedule")

                for task in tasks:
                    next_run = task.get("next_run", "N/A")
                    if next_run:
                        from datetime import datetime

                        try:
                            dt = datetime.fromisoformat(next_run)
                            next_run = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            pass

                    table.add_row(
                        task["id"], task["name"], next_run, task.get("trigger", "")
                    )

                console.print(table)
            else:
                info("No scheduled tasks")
        else:
            info("Scheduler is not running")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@scheduler_cli.command(name="add")
@click.argument("task_id")
@click.argument("cron_expression")
@click.option("--type", "-t", type=click.Choice(["backup", "health-check", "command"]), required=True, help="Task type")
@click.option("--target", help="Target instance/environment for the task")
@click.option("--command", "-c", help="Command to execute (for command type)")
@click.pass_context
def scheduler_add(ctx, task_id, cron_expression, type, target, command):
    """Add a scheduled task.

    Example: odoo-manager scheduler add backup-prod "0 2 * * *" --type backup --target production
    """
    try:
        scheduler = SchedulerManager()

        if type == "backup":
            if not target:
                error("--target is required for backup tasks")
                ctx.exit(1)

            backup_mgr = BackupManager()

            def backup_func(environment):
                info(f"Running scheduled backup for {environment}...")
                backup_mgr.backup_database(environment)

            scheduler.add_task(task_id, backup_func, cron_expression, name=f"Backup {target}")

        elif type == "health-check":
            if not target:
                error("--target is required for health-check tasks")
                ctx.exit(1)

            monitor = HealthMonitor()
            inst_mgr = InstanceManager()

            def health_check_func(instance_name):
                from odoo_manager.utils.notifications import send_alert

                instance = inst_mgr.get_instance(instance_name)
                health = monitor.check_instance(instance)

                if health.status.value == "critical":
                    send_alert(
                        f"Critical: {instance_name} health check failed",
                        details={"instance": instance_name, "health": health.status},
                    )

            scheduler.add_task(
                task_id, health_check_func, cron_expression, name=f"Health check {target}"
            )

        elif type == "command":
            if not command:
                error("--command is required for command tasks")
                ctx.exit(1)

            def command_func():
                import subprocess

                info(f"Running scheduled command: {command}")
                subprocess.run(command, shell=True, check=True)

            scheduler.add_task(task_id, command_func, cron_expression, name=command)

        success(f"Task '{task_id}' added")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@scheduler_cli.command(name="remove")
@click.argument("task_id")
@click.pass_context
def scheduler_remove(ctx, task_id):
    """Remove a scheduled task.

    Example: odoo-manager scheduler remove backup-prod
    """
    try:
        scheduler = SchedulerManager()

        if not scheduler.get_task(task_id):
            error(f"Task not found: {task_id}")
            ctx.exit(1)

        scheduler.remove_task(task_id)
        success(f"Task '{task_id}' removed")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@scheduler_cli.command(name="run")
@click.argument("task_id")
@click.pass_context
def scheduler_run(ctx, task_id):
    """Run a scheduled task immediately.

    Example: odoo-manager scheduler run backup-prod
    """
    try:
        scheduler = SchedulerManager()

        if not scheduler.get_task(task_id):
            error(f"Task not found: {task_id}")
            ctx.exit(1)

        info(f"Running task '{task_id}'...")
        scheduler.run_task_now(task_id)
        success(f"Task '{task_id}' completed")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@scheduler_cli.command(name="logs")
@click.option("--tail", "-n", type=int, default=50, help="Number of lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.pass_context
def scheduler_logs(ctx, tail, follow):
    """Show scheduler logs.

    Example: odoo-manager scheduler logs --follow
    """
    try:
        from odoo_manager.constants import SCHEDULER_LOG_FILE

        log_file = SCHEDULER_LOG_FILE

        if not log_file.exists():
            info("No scheduler logs found")
            return

        if follow:
            import subprocess

            subprocess.run(["tail", "-f", str(log_file)])
        else:
            result = subprocess.run(
                ["tail", "-n", str(tail), str(log_file)],
                capture_output=True,
                text=True,
            )
            console.print(result.stdout)

    except Exception as e:
        error(str(e))
        ctx.exit(1)
