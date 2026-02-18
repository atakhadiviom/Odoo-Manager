"""
Main CLI entry point for Odoo Manager.
"""

from pathlib import Path

import click
from rich.console import Console

from odoo_manager import __version__
from odoo_manager.commands.instance import instance_cli
from odoo_manager.commands.db import db_cli
from odoo_manager.commands.module import module_cli
from odoo_manager.commands.logs import logs_cli
from odoo_manager.commands.backup import backup_cli
from odoo_manager.commands.config import config_cli
from odoo_manager.commands.shell import shell_cmd
from odoo_manager.commands.git import git_cli
from odoo_manager.commands.environment import env_cli
from odoo_manager.commands.deploy import deploy_cli
from odoo_manager.commands.monitor import monitor_cli
from odoo_manager.commands.scheduler import scheduler_cli
from odoo_manager.commands.ssh import ssh_cli
from odoo_manager.commands.user import user_cli
from odoo_manager.commands.ssl import ssl_cli
from odoo_manager.commands.tui import tui_cli
from odoo_manager.constants import DEFAULT_CONFIG_FILE
from odoo_manager.utils.output import success, error

console = Console()


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=False),
    default=str(DEFAULT_CONFIG_FILE),
    help="Path to configuration file",
)
@click.option("--verbose", "-v", is_flag=True, help="Increase verbosity")
@click.option("--json", is_flag=True, help="Output in JSON format")
@click.pass_context
def main(ctx, config, verbose, json):
    """
    Odoo Manager - A local Odoo instance management tool.

    Manage Odoo instances similar to odoo.sh, but for local/server-based deployments.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = Path(config)
    ctx.obj["verbose"] = verbose
    ctx.obj["json"] = json


@main.command()
def version():
    """Show version information."""
    console.print(f"Odoo Manager version [cyan]{__version__}[/cyan]")


# Register command groups
main.add_command(instance_cli)
main.add_command(db_cli)
main.add_command(module_cli)
main.add_command(backup_cli)
main.add_command(logs_cli)
main.add_command(config_cli)
main.add_command(shell_cmd)
main.add_command(git_cli)
main.add_command(env_cli)
main.add_command(deploy_cli)
main.add_command(monitor_cli)
main.add_command(scheduler_cli)
main.add_command(ssh_cli)
main.add_command(user_cli)
main.add_command(ssl_cli)
main.add_command(tui_cli)


if __name__ == "__main__":
    main()
