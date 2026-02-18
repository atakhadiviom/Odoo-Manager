"""
Module commands for the CLI.
"""

import click
from rich.console import Console
from rich.table import Table

from odoo_manager.core.instance import InstanceManager
from odoo_manager.core.module import ModuleManager
from odoo_manager.exceptions import InstanceNotFoundError, ModuleError, ModuleNotFoundError
from odoo_manager.utils.output import success, error, warning, info

console = Console()


@click.group(name="module")
@click.option("--instance", "-i", help="Instance name (defaults to first available)")
@click.pass_context
def module_cli(ctx, instance):
    """Manage Odoo modules."""
    ctx.ensure_object(dict)
    ctx.obj["instance"] = instance


@module_cli.command(name="ls")
@click.option("--state", "-s", help="Filter by state (installed, uninstalled, to upgrade, etc.)")
@click.option("--installed", "-I", is_flag=True, help="Show only installed modules")
@click.option("--all", "-a", is_flag=True, help="Show all modules (not just core/addons)")
@click.pass_context
def list_modules(ctx, state, installed, all):
    """List Odoo modules."""
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

        if not instance.is_running():
            error(f"Instance '{instance_name}' is not running. Start it first.")
            return

        module_manager = ModuleManager(instance.config)

        # Default to showing installed modules if no filter specified
        if not state and not installed:
            installed = True

        modules = module_manager.list_modules(state=state, installed_only=installed)

        if not modules:
            info("No modules found.")
            return

        table = Table(title=f"Modules in '{instance_name}'")
        table.add_column("Name", style="cyan")
        table.add_column("State", style="green")
        table.add_column("Version", style="yellow")
        table.add_column("Summary", style="white")

        for module in modules:
            # Format state
            state_text = module["state"]
            if state_text == "installed":
                state_text = "[green]installed[/green]"
            elif state_text == "uninstalled":
                state_text = "[dim]uninstalled[/dim]"
            elif state_text == "to upgrade":
                state_text = "[yellow]to upgrade[/yellow]"

            table.add_row(
                module["name"],
                state_text,
                module.get("latest_version", "N/A"),
                module.get("shortdesc", "")[:50] if module.get("shortdesc") else "",
            )

        console.print(table)

    except InstanceNotFoundError:
        error(f"Instance '{instance_name}' not found")
    except ModuleError as e:
        error(f"Module error: {e}")


@module_cli.command()
@click.argument("name")
@click.option("--instance", "-i", help="Instance name")
@click.pass_context
def install(ctx, name, instance):
    """Install a module."""
    # Merge instance from context if not provided
    if not instance:
        instance = ctx.obj.get("instance")

    if not instance:
        error("Please specify an instance with --instance")
        return

    manager = InstanceManager()
    try:
        inst = manager.get_instance(instance)

        if not inst.is_running():
            error(f"Instance '{instance}' is not running. Start it first.")
            return

        module_manager = ModuleManager(inst.config)
        info(f"Installing module '{name}'...")
        module_manager.install_module(name)
        success(f"Module '{name}' installed successfully!")
    except InstanceNotFoundError:
        error(f"Instance '{instance}' not found")
    except ModuleNotFoundError:
        error(f"Module '{name}' not found")
    except ModuleError as e:
        error(f"Failed to install module: {e}")


@module_cli.command()
@click.argument("name")
@click.option("--instance", "-i", help="Instance name")
@click.pass_context
def uninstall(ctx, name, instance):
    """Uninstall a module."""
    # Merge instance from context if not provided
    if not instance:
        instance = ctx.obj.get("instance")

    if not instance:
        error("Please specify an instance with --instance")
        return

    manager = InstanceManager()
    try:
        inst = manager.get_instance(instance)

        if not inst.is_running():
            error(f"Instance '{instance}' is not running. Start it first.")
            return

        module_manager = ModuleManager(inst.config)
        info(f"Uninstalling module '{name}'...")
        module_manager.uninstall_module(name)
        success(f"Module '{name}' uninstalled successfully!")
    except InstanceNotFoundError:
        error(f"Instance '{instance}' not found")
    except ModuleNotFoundError:
        error(f"Module '{name}' not found")
    except ModuleError as e:
        error(f"Failed to uninstall module: {e}")


@module_cli.command()
@click.argument("name", required=False)
@click.option("--instance", "-i", help="Instance name")
@click.option("--all", "-a", is_flag=True, help="Update all modules")
@click.pass_context
def update(ctx, name, instance, all):
    """Update a module or all modules."""
    # Merge instance from context if not provided
    if not instance:
        instance = ctx.obj.get("instance")

    if not instance:
        error("Please specify an instance with --instance")
        return

    if not name and not all:
        error("Please specify a module name or use --all to update all modules")
        return

    manager = InstanceManager()
    try:
        inst = manager.get_instance(instance)

        if not inst.is_running():
            error(f"Instance '{instance}' is not running. Start it first.")
            return

        module_manager = ModuleManager(inst.config)

        if all:
            info("Updating all modules...")
            module_manager.update_module(None)
            success("All modules updated successfully!")
        else:
            info(f"Updating module '{name}'...")
            module_manager.update_module(name)
            success(f"Module '{name}' updated successfully!")
    except InstanceNotFoundError:
        error(f"Instance '{instance}' not found")
    except ModuleNotFoundError:
        error(f"Module '{name}' not found")
    except ModuleError as e:
        error(f"Failed to update module: {e}")


@module_cli.command()
@click.argument("name")
@click.option("--instance", "-i", help="Instance name")
@click.pass_context
def info_cmd(ctx, name, instance):
    """Show detailed information about a module."""
    # Merge instance from context if not provided
    if not instance:
        instance = ctx.obj.get("instance")

    if not instance:
        error("Please specify an instance with --instance")
        return

    manager = InstanceManager()
    try:
        inst = manager.get_instance(instance)

        if not inst.is_running():
            error(f"Instance '{instance}' is not running. Start it first.")
            return

        module_manager = ModuleManager(inst.config)
        module = module_manager.get_module(name)

        if not module:
            error(f"Module '{name}' not found")
            return

        console.print(f"\n[bold cyan]Module: {module['name']}[/bold cyan]")
        console.print(f"  State:          {module['state']}")
        console.print(f"  Version:        {module.get('latest_version', 'N/A')}")
        console.print(f"  Author:         {module.get('author', 'N/A')}")
        console.print(f"  Summary:        {module.get('shortdesc', 'N/A')}")
        if module.get('summary'):
            console.print(f"  Description:    {module['summary'][:200]}")
        console.print()

    except InstanceNotFoundError:
        error(f"Instance '{instance}' not found")
    except ModuleError as e:
        error(f"Failed to get module info: {e}")
