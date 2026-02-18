"""
Backup commands for the CLI.
"""

import click
from humanfriendly import format_size
from pathlib import Path
from rich.console import Console
from rich.table import Table

from odoo_manager.core.backup import BackupManager
from odoo_manager.core.instance import InstanceManager
from odoo_manager.core.scheduler import SchedulerManager
from odoo_manager.exceptions import BackupError, InstanceNotFoundError
from odoo_manager.utils.output import success, error, warning, info

console = Console()


@click.group(name="backup")
def backup_cli():
    """Manage backups."""
    pass


@backup_cli.command(name="ls")
@click.option("--instance", "-i", help="Filter by instance name")
def list_backups(instance):
    """List all backups."""
    manager = BackupManager()

    try:
        backups = manager.list_backups(instance)

        if not backups:
            info("No backups found.")
            return

        table = Table(title="Backups")
        table.add_column("Filename", style="cyan")
        table.add_column("Instance", style="green")
        table.add_column("Database", style="yellow")
        table.add_column("Date", style="magenta")
        table.add_column("Size", style="blue")

        for backup in backups:
            table.add_row(
                backup["filename"],
                backup["instance"],
                backup["database"],
                backup["date"],
                format_size(backup["size"]),
            )

        console.print(table)

    except BackupError as e:
        error(f"Failed to list backups: {e}")


@backup_cli.command()
@click.argument("instance")
@click.option("--database", "-d", help="Database name (defaults to instance db_name)")
@click.option("--name", "-n", help="Custom backup name")
def create(instance, database, name):
    """Create a backup of an instance."""
    manager = BackupManager()

    try:
        backup_path = manager.create_backup(instance, database, name)
        success(f"Backup created: {backup_path}")
    except InstanceNotFoundError:
        error(f"Instance '{instance}' not found")
    except BackupError as e:
        error(f"Failed to create backup: {e}")


@backup_cli.command()
@click.argument("backup_file")
@click.argument("instance")
@click.option("--database", "-d", help="Target database name (defaults to instance db_name)")
@click.option("--force", "-f", is_flag=True, help="Force restore without confirmation")
def restore(backup_file, instance, database, force):
    """Restore a backup to an instance."""
    manager = BackupManager()
    backup_path = Path(backup_file)

    if not backup_path.is_absolute():
        # Try to find in backup directory
        backup_path = manager.get_backup_dir() / backup_file

    try:
        if not force:
            if not click.confirm(f"Restore backup to instance '{instance}'?"):
                info("Operation cancelled.")
                return

        manager.restore_backup(backup_path, instance, database)
        success(f"Backup restored to instance '{instance}'")
    except BackupError as e:
        error(f"Failed to restore backup: {e}")


@backup_cli.command()
@click.argument("backup_file")
@click.option("--force", "-f", is_flag=True, help="Force deletion without confirmation")
def delete(backup_file, force):
    """Delete a backup file."""
    manager = BackupManager()
    backup_path = Path(backup_file)

    if not backup_path.is_absolute():
        backup_path = manager.get_backup_dir() / backup_file

    try:
        if not force:
            if not click.confirm(f"Delete backup '{backup_file}'?"):
                info("Operation cancelled.")
                return

        manager.delete_backup(backup_path)
        success(f"Backup deleted: {backup_file}")
    except BackupError as e:
        error(f"Failed to delete backup: {e}")


@backup_cli.command()
@click.argument("instance")
@click.option("--retention", "-r", type=int, help="Retention days in days")
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be deleted without deleting")
def cleanup(instance, retention, dry_run):
    """Remove old backups based on retention policy."""
    manager = BackupManager()

    try:
        if dry_run:
            backups = manager.list_backups(instance)
            retention_days = retention or manager.config.settings.backup_retention_days
            cutoff_date = backups[0]["date"] if backups else None

            info(f"Would delete backups older than {retention_days} days")
            info(f"(This is a dry run, use without --dry-run to actually delete)")
            return

        removed = manager.cleanup_old_backups(instance, retention)

        if removed:
            success(f"Removed {len(removed)} old backup(s)")
            for path in removed:
                info(f"  - {path.name}")
        else:
            info("No old backups to remove")

    except BackupError as e:
        error(f"Failed to cleanup backups: {e}")


@backup_cli.command(name="schedule")
@click.argument("environment")
@click.option("--cron", "-c", help="Cron expression (e.g., '0 2 * * *' for daily at 2 AM)")
@click.option("--unschedule", "-u", is_flag=True, help="Remove scheduled backup")
@click.pass_context
def backup_schedule(ctx, environment, cron, unschedule):
    """Schedule automated backups for an environment.

    Example: odoo-manager backup schedule production --cron "0 2 * * *"
    """
    try:
        task_id = f"backup-{environment}"

        if unschedule:
            scheduler = SchedulerManager()
            if scheduler.get_task(task_id):
                scheduler.remove_task(task_id)
                success(f"Removed scheduled backup for '{environment}'")
            else:
                info(f"No scheduled backup found for '{environment}'")
            return

        if not cron:
            error("--cron is required (use --unschedule to remove)")
            ctx.exit(1)

        # Validate cron expression
        parts = cron.split()
        if len(parts) != 5:
            error("Invalid cron expression. Must have 5 parts: minute hour day month day_of_week")
            ctx.exit(1)

        scheduler = SchedulerManager()
        backup_mgr = BackupManager()

        def backup_func(env):
            info(f"Running scheduled backup for {env}...")
            backup_mgr.backup_database(env)

        scheduler.add_task(
            task_id=task_id,
            func=backup_func,
            cron_expression=cron,
            name=f"Backup {environment}",
            kwargs={"env": environment},
        )

        success(f"Scheduled backup for '{environment}' with cron: {cron}")
        info("Note: The scheduler must be running for backups to execute")
        info("Start the scheduler with: odoo-manager scheduler start")

    except Exception as e:
        error(f"Failed to schedule backup: {e}")
        ctx.exit(1)
