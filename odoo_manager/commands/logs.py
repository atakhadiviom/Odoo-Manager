"""
Log viewing commands for the CLI.
"""

import time
import click
from rich.console import Console
from rich.live import Live

from odoo_manager.core.instance import InstanceManager
from odoo_manager.exceptions import InstanceNotFoundError
from odoo_manager.utils.output import error

console = Console()


@click.group(name="logs")
def logs_cli():
    """View instance logs."""
    pass


@logs_cli.command()
@click.argument("name")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--tail", "-n", default=100, help="Number of lines to show")
@click.option("--service", "-s", type=click.Choice(["odoo", "postgres", "all"]), default="odoo", help="Service to show logs for")
def show(name, follow, tail, service):
    """Show logs for an instance."""
    manager = InstanceManager()

    try:
        instance = manager.get_instance(name)

        if not instance.is_running():
            error(f"Instance '{name}' is not running")
            return

        if instance.config.deployment_type == "docker":
            if follow:
                _show_logs_follow_docker(instance, tail, service)
            else:
                _show_logs_docker(instance, tail, service)
        else:
            error("Log viewing not implemented for source deployment")

    except InstanceNotFoundError:
        error(f"Instance '{name}' not found")


def _show_logs_docker(instance, tail, service):
    """Show Docker logs without follow mode."""
    import subprocess

    if service == "all":
        # Show logs from both services
        services = ["odoo", "postgres"]
    else:
        services = [service]

    for svc in services:
        container_name = instance.deployer._container_names.get(svc)
        if not container_name:
            continue

        console.print(f"\n[bold cyan]Logs for {svc}:[/bold cyan]")

        cmd = ["docker", "logs", "--tail", str(tail), container_name]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(result.stdout)
        else:
            error(f"Failed to get logs for {svc}: {result.stderr}")


def _show_logs_follow_docker(instance, tail, service):
    """Show Docker logs with follow mode."""
    import subprocess

    if service == "all":
        services = ["odoo", "postgres"]
    else:
        services = [service]

    # For follow mode, we'll stream the logs
    processes = []

    try:
        for svc in services:
            container_name = instance.deployer._container_names.get(svc)
            if not container_name:
                continue

            console.print(f"\n[bold cyan]Following logs for {svc} (Ctrl+C to stop):[/bold cyan]")

            cmd = ["docker", "logs", "--follow", "--tail", str(tail), container_name]
            process = subprocess.Popen(cmd, text=True)
            processes.append(process)

        # Wait for interrupt
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped following logs[/yellow]")
        for process in processes:
            process.terminate()
