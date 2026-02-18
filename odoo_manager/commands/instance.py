"""
Instance commands for the CLI.
"""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from odoo_manager.core.instance import InstanceManager
from odoo_manager.exceptions import InstanceNotFoundError, OdooManagerError
from odoo_manager.utils.output import success, error, warning, info


@click.group(name="instance")
def instance_cli():
    """Manage Odoo instances."""
    pass


@instance_cli.command(name="list")
def list_instances():
    """List all Odoo instances."""
    manager = InstanceManager()
    instances = manager.list_instances()

    if not instances:
        info("No instances found. Use 'odoo-manager instance create' to create one.")
        return

    console = Console()
    table = Table(title="Odoo Instances")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Edition", style="yellow")
    table.add_column("Type", style="magenta")
    table.add_column("Port", style="blue")
    table.add_column("Database", style="blue")
    table.add_column("Status", style="bold")
    table.add_column("Workers", style="dim")

    for inst in instances:
        status = "[green]Running[/green]" if inst.is_running() else "[red]Stopped[/red]"
        table.add_row(
            inst.config.name,
            inst.config.version,
            inst.config.edition,
            inst.config.deployment_type,
            str(inst.config.port),
            inst.config.db_name,
            status,
            str(inst.config.workers),
        )

    console.print(table)


@instance_cli.command(name="ls")
def ls():
    """List all Odoo instances (alias for list)."""
    ctx = click.get_current_context()
    ctx.invoke(list_instances)


@instance_cli.command()
@click.argument("name")
@click.option("--version", "-v", default="17.0", help="Odoo version")
@click.option("--edition", "-e", type=click.Choice(["community", "enterprise"]), default="community", help="Odoo edition")
@click.option("--port", "-p", type=int, default=8069, help="Port to expose")
@click.option("--workers", "-w", type=int, default=4, help="Number of workers")
@click.option("--db-name", "-d", help="Database name (defaults to instance name)")
@click.option("--deployment", type=click.Choice(["docker", "source"]), default="docker", help="Deployment type")
def create(name, version, edition, port, workers, db_name, deployment):
    """Create a new Odoo instance."""
    manager = InstanceManager()

    try:
        instance = manager.create_instance(
            name=name,
            version=version,
            edition=edition,
            deployment_type=deployment,
            port=port,
            workers=workers,
            db_name=db_name,
        )
        success(f"Instance '{name}' created successfully!")
        info(f"Data directory: {instance.data_dir / name}")
        info(f"Use 'odoo-manager instance start {name}' to start the instance.")
    except OdooManagerError as e:
        error(f"Failed to create instance: {e}")


@instance_cli.command()
@click.argument("name")
def start(name):
    """Start an Odoo instance."""
    manager = InstanceManager()

    try:
        instance = manager.get_instance(name)
        instance.start()
        success(f"Instance '{name}' started successfully!")
        info(f"Access at: http://localhost:{instance.config.port}")
    except OdooManagerError as e:
        error(f"Failed to start instance: {e}")


@instance_cli.command()
@click.argument("name")
def stop(name):
    """Stop an Odoo instance."""
    manager = InstanceManager()

    try:
        instance = manager.get_instance(name)
        instance.stop()
        success(f"Instance '{name}' stopped successfully!")
    except OdooManagerError as e:
        error(f"Failed to stop instance: {e}")


@instance_cli.command()
@click.argument("name")
def restart(name):
    """Restart an Odoo instance."""
    manager = InstanceManager()

    try:
        instance = manager.get_instance(name)
        instance.restart()
        success(f"Instance '{name}' restarted successfully!")
    except OdooManagerError as e:
        error(f"Failed to restart instance: {e}")


@instance_cli.command()
@click.argument("name")
def status(name):
    """Show the status of an Odoo instance."""
    manager = InstanceManager()

    try:
        instance = manager.get_instance(name)
        is_running = instance.is_running()
        status_text = "[green]Running[/green]" if is_running else "[red]Stopped[/red]"

        console = Console()
        console.print(f"\nInstance: [cyan]{name}[/cyan]")
        console.print(f"Status: {status_text}")
        console.print(f"Version: {instance.config.version}")
        console.print(f"Edition: {instance.config.edition}")
        console.print(f"Deployment: {instance.config.deployment_type}")
        console.print(f"Port: {instance.config.port}")
        console.print(f"Database: {instance.config.db_name}")
        console.print(f"Workers: {instance.config.workers}")

        if instance.config.deployment_type == "docker":
            info = instance.deployer.get_container_info()
            if info.get("odoo"):
                console.print(f"\n[dim]Odoo Container: {info['odoo']['id']} ({info['odoo']['status']})[/dim]")
            if info.get("postgres"):
                console.print(f"[dim]Postgres Container: {info['postgres']['id']} ({info['postgres']['status']})[/dim]")
    except InstanceNotFoundError:
        error(f"Instance '{name}' not found")
    except OdooManagerError as e:
        error(f"Failed to get status: {e}")


@instance_cli.command()
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Force removal without confirmation")
def rm(name, force):
    """Remove an Odoo instance."""
    manager = InstanceManager()

    try:
        instance = manager.get_instance(name)

        if not force:
            if not click.confirm(f"Are you sure you want to remove instance '{name}'?"):
                info("Operation cancelled.")
                return

        manager.remove_instance(name)
        success(f"Instance '{name}' removed successfully!")
    except InstanceNotFoundError:
        error(f"Instance '{name}' not found")
    except OdooManagerError as e:
        error(f"Failed to remove instance: {e}")


@instance_cli.command(name="remove")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Force removal without confirmation")
def remove_instance(name, force):
    """Remove an Odoo instance (alias for rm)."""
    # Call the rm command
    ctx = click.get_current_context()
    ctx.invoke(rm, name=name, force=force)


@instance_cli.command()
@click.argument("name")
def info(name):
    """Show detailed information about an instance."""
    manager = InstanceManager()

    try:
        instance = manager.get_instance(name)
        console = Console()

        # Print detailed info
        console.print(f"\n[bold cyan]Instance: {name}[/bold cyan]")
        console.print(f"  Version:        {instance.config.version}")
        console.print(f"  Edition:        {instance.config.edition}")
        console.print(f"  Deployment:     {instance.config.deployment_type}")
        console.print(f"  Status:         {'[green]Running[/green]' if instance.is_running() else '[red]Stopped[/red]'}")
        console.print()
        console.print("[bold]Network[/bold]")
        console.print(f"  Port:           {instance.config.port}")
        console.print(f"  URL:            http://localhost:{instance.config.port}")
        console.print()
        console.print("[bold]Database[/bold]")
        console.print(f"  Name:           {instance.config.db_name}")
        console.print(f"  Host:           {instance.config.db_host}")
        console.print(f"  Port:           {instance.config.db_port}")
        console.print(f"  User:           {instance.config.db_user}")
        console.print()
        console.print("[bold]Configuration[/bold]")
        console.print(f"  Workers:        {instance.config.workers}")
        console.print(f"  Max Cron:       {instance.config.max_cron_threads}")
        console.print(f"  DB Max Conn:    {instance.config.db_maxconn}")
        console.print(f"  Without Demo:   {instance.config.without_demo}")
        console.print()
        console.print("[bold]Paths[/bold]")
        console.print(f"  Data Dir:       {instance.data_dir / name}")
        console.print()
    except InstanceNotFoundError:
        error(f"Instance '{name}' not found")
    except OdooManagerError as e:
        error(f"Failed to get info: {e}")
