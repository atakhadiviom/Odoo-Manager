"""
Database commands for the CLI.
"""

from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from odoo_manager.core.database import DatabaseManager
from odoo_manager.core.instance import InstanceManager
from odoo_manager.exceptions import DatabaseError, DatabaseNotFoundError, InstanceNotFoundError
from odoo_manager.utils.output import success, error, warning, info

console = Console()


@click.group(name="db")
@click.option("--instance", "-i", help="Instance name (defaults to first available)")
@click.pass_context
def db_cli(ctx, instance):
    """Manage Odoo databases."""
    ctx.ensure_object(dict)
    ctx.obj["instance"] = instance


@db_cli.command(name="ls")
@click.pass_context
def list_databases(ctx):
    """List all databases."""
    instance_name = ctx.obj.get("instance")

    if not instance_name:
        # Try to get the first available instance
        manager = InstanceManager()
        instances = manager.list_instances()
        if not instances:
            error("No instances found. Create one first with 'odoo-manager instance create'.")
            return
        instance_name = instances[0].config.name
        info(f"No instance specified, using '{instance_name}'")

    manager = InstanceManager()
    try:
        instance = manager.get_instance(instance_name)
        db_manager = DatabaseManager(instance.config, instance.data_dir)

        databases = db_manager.list_databases()

        if not databases:
            info("No databases found.")
            return

        table = Table(title=f"Databases in '{instance_name}'")
        table.add_column("Name", style="cyan")
        table.add_column("Size", style="green")

        for db in databases:
            table.add_row(db["name"], db["size"])

        console.print(table)
    except InstanceNotFoundError:
        error(f"Instance '{instance_name}' not found")
    except DatabaseError as e:
        error(f"Database error: {e}")


@db_cli.command()
@click.argument("name")
@click.pass_context
def create(ctx, name):
    """Create a new database."""
    instance_name = ctx.obj.get("instance")

    if not instance_name:
        error("Please specify an instance with --instance")
        return

    manager = InstanceManager()
    try:
        instance = manager.get_instance(instance_name)
        db_manager = DatabaseManager(instance.config, instance.data_dir)

        db_manager.create_database(name)
        success(f"Database '{name}' created successfully!")
        info(f"You can now initialize it with Odoo or restore a backup.")
    except InstanceNotFoundError:
        error(f"Instance '{instance_name}' not found")
    except DatabaseError as e:
        error(f"Failed to create database: {e}")


@db_cli.command()
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Force drop without confirmation")
@click.pass_context
def drop(ctx, name, force):
    """Drop a database."""
    instance_name = ctx.obj.get("instance")

    if not instance_name:
        error("Please specify an instance with --instance")
        return

    manager = InstanceManager()
    try:
        instance = manager.get_instance(instance_name)
        db_manager = DatabaseManager(instance.config, instance.data_dir)

        if not force:
            if not click.confirm(f"Are you sure you want to drop database '{name}'? This cannot be undone."):
                info("Operation cancelled.")
                return

        db_manager.drop_database(name)
        success(f"Database '{name}' dropped successfully!")
    except InstanceNotFoundError:
        error(f"Instance '{instance_name}' not found")
    except DatabaseNotFoundError:
        error(f"Database '{name}' not found")
    except DatabaseError as e:
        error(f"Failed to drop database: {e}")


@db_cli.command()
@click.argument("name")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
def backup(ctx, name, output):
    """Backup a database."""
    instance_name = ctx.obj.get("instance")

    if not instance_name:
        error("Please specify an instance with --instance")
        return

    # Generate default output path if not specified
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"{name}_{timestamp}.dump"

    output_path = Path(output)

    manager = InstanceManager()
    try:
        instance = manager.get_instance(instance_name)
        db_manager = DatabaseManager(instance.config, instance.data_dir)

        info(f"Backing up database '{name}'...")
        db_manager.backup_database(name, output_path)
        success(f"Database '{name}' backed up to '{output_path}'")
    except InstanceNotFoundError:
        error(f"Instance '{instance_name}' not found")
    except DatabaseNotFoundError:
        error(f"Database '{name}' not found")
    except DatabaseError as e:
        error(f"Failed to backup database: {e}")


@db_cli.command()
@click.argument("file")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Force restore without confirmation")
@click.pass_context
def restore(ctx, file, name, force):
    """Restore a database from a backup file."""
    instance_name = ctx.obj.get("instance")

    if not instance_name:
        error("Please specify an instance with --instance")
        return

    backup_path = Path(file)

    if not backup_path.exists():
        error(f"Backup file '{file}' not found")
        return

    manager = InstanceManager()
    try:
        instance = manager.get_instance(instance_name)
        db_manager = DatabaseManager(instance.config, instance.data_dir)

        if not force:
            if not click.confirm(f"Restore database '{name}' from '{file}'?"):
                info("Operation cancelled.")
                return

        info(f"Restoring database '{name}'...")
        db_manager.restore_database(backup_path, name)
        success(f"Database '{name}' restored successfully!")
    except InstanceNotFoundError:
        error(f"Instance '{instance_name}' not found")
    except DatabaseError as e:
        error(f"Failed to restore database: {e}")


@db_cli.command()
@click.argument("source")
@click.argument("target")
@click.pass_context
def duplicate(ctx, source, target):
    """Duplicate a database."""
    instance_name = ctx.obj.get("instance")

    if not instance_name:
        error("Please specify an instance with --instance")
        return

    manager = InstanceManager()
    try:
        instance = manager.get_instance(instance_name)
        db_manager = DatabaseManager(instance.config, instance.data_dir)

        info(f"Duplicating database '{source}' to '{target}'...")
        db_manager.duplicate_database(source, target)
        success(f"Database duplicated successfully!")
        info(f"New database '{target}' created from '{source}'")
    except InstanceNotFoundError:
        error(f"Instance '{instance_name}' not found")
    except DatabaseNotFoundError:
        error(f"Source database '{source}' not found")
    except DatabaseError as e:
        error(f"Failed to duplicate database: {e}")
