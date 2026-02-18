"""
Shell command for accessing the Odoo shell.
"""

import click
from rich.console import Console

from odoo_manager.core.instance import InstanceManager
from odoo_manager.exceptions import InstanceNotFoundError, InstanceStateError
from odoo_manager.utils.output import error, info

console = Console()


@click.command()
@click.argument("name")
@click.option("--database", "-d", help="Database name (defaults to instance db_name)")
@click.option("--no-deps", is_flag=True, help="Don't check if instance is running")
def shell(name, database, no_deps):
    """Open an Odoo shell for the instance."""
    manager = InstanceManager()

    try:
        instance = manager.get_instance(name)

        if not no_deps and not instance.is_running():
            error(f"Instance '{name}' is not running")
            info("Use --no-deps to skip this check (if using a custom setup)")
            return

        db_name = database or instance.config.db_name

        if instance.config.deployment_type == "docker":
            _open_docker_shell(instance, db_name)
        else:
            error("Shell access not implemented for source deployment")

    except InstanceNotFoundError:
        error(f"Instance '{name}' not found")
    except InstanceStateError as e:
        error(str(e))


def _open_docker_shell(instance, database):
    """Open shell in Docker container."""
    import subprocess
    import sys

    container_name = instance.deployer._container_names["odoo"]
    db_name = database or instance.config.db_name

    console.print(f"[cyan]Opening Odoo shell for '{instance.config.name}'...[/cyan]")
    console.print("[dim]Press Ctrl+D to exit[/dim]\n")

    cmd = [
        "docker", "exec", "-it", container_name,
        "python3", "-c",
        f"import odoo; odoo.cli.main(['--shell', '-d', '{db_name}'])"
    ]

    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        console.print("\n[yellow]Shell exited[/yellow]")
    except Exception as e:
        error(f"Failed to open shell: {e}")
        sys.exit(1)


# Register as a command
shell_cmd = shell
