"""
Configuration management commands for the CLI.
"""

from pathlib import Path

import click
from rich.console import Console

from odoo_manager.config import Config, InstancesFile
from odoo_manager.constants import DEFAULT_CONFIG_FILE, DEFAULT_CONFIG_DIR
from odoo_manager.exceptions import ConfigError
from odoo_manager.utils.output import success, error, info

console = Console()


@click.group(name="config")
def config_cli():
    """Manage configuration."""
    pass


@config_cli.command()
def show():
    """Show current configuration."""
    try:
        config = Config.load()

        console.print(f"\n[bold cyan]Odoo Manager Configuration[/bold cyan]")
        console.print(f"Config file: {DEFAULT_CONFIG_FILE}")
        console.print()

        console.print("[bold]Settings[/bold]")
        console.print(f"  Data dir:      {config.settings.data_dir}")
        console.print(f"  Backup dir:    {config.settings.backup_dir}")
        console.print(f"  Log dir:       {config.settings.log_dir}")
        console.print(f"  Default ed.:   {config.settings.default_edition}")
        console.print(f"  Default dep.:  {config.settings.default_deployment}")
        console.print(f"  Odoo version:  {config.settings.default_odoo_version}")
        console.print()

        console.print("[bold]PostgreSQL[/bold]")
        console.print(f"  Host:          {config.postgres.host}")
        console.print(f"  Port:          {config.postgres.port}")
        console.print(f"  User:          {config.postgres.user}")
        console.print(f"  Superuser:     {config.postgres.superuser}")
        console.print()

        console.print("[bold]Backup[/bold]")
        console.print(f"  Retention:     {config.backup.retention_days} days")
        console.print(f"  Compression:   {config.backup.compression}")
        console.print(f"  Format:        {config.backup.format}")
        console.print()

    except ConfigError as e:
        error(f"Failed to load configuration: {e}")


@config_cli.command()
@click.option("--key", "-k", required=True, help="Configuration key (e.g., settings.default_edition)")
@click.option("--value", "-v", required=True, help="New value")
def set(key, value):
    """Set a configuration value."""
    try:
        config = Config.load()

        # Parse the key path (e.g., "settings.default_edition")
        parts = key.split(".")
        if len(parts) != 2:
            error("Key must be in format 'section.key' (e.g., 'settings.default_edition')")
            return

        section, attr = parts

        if section == "settings":
            setattr(config.settings, attr, value)
        elif section == "postgres":
            setattr(config.postgres, attr, value)
        elif section == "backup":
            setattr(config.backup, attr, value)
        else:
            error(f"Unknown configuration section: {section}")
            return

        config.save()
        success(f"Configuration updated: {key} = {value}")

    except ConfigError as e:
        error(f"Failed to update configuration: {e}")
    except AttributeError:
        error(f"Unknown configuration key: {key}")


@config_cli.command()
def path():
    """Show configuration file path."""
    console.print(f"Config file: [cyan]{DEFAULT_CONFIG_FILE}[/cyan]")
    console.print(f"Instances file: [cyan]{DEFAULT_CONFIG_DIR / 'instances.yaml'}[/cyan]")


@config_cli.command()
def init():
    """Initialize configuration with default values."""
    if DEFAULT_CONFIG_FILE.exists():
        if not click.confirm(f"Config file exists at {DEFAULT_CONFIG_FILE}. Overwrite?"):
            info("Operation cancelled.")
            return

    config = Config()
    config.save()

    # Create instances file if it doesn't exist
    instances_file = DEFAULT_CONFIG_DIR / "instances.yaml"
    if not instances_file.exists():
        instances = InstancesFile()
        instances.save(InstancesConfig())

    success(f"Configuration initialized at {DEFAULT_CONFIG_FILE}")
    info(f"Edit the file to customize your settings")
