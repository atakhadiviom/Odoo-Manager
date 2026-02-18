"""
Main CLI entry point for Odoo Manager.
"""

import os
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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


def show_interactive_menu():
    """Show interactive menu for Odoo Manager."""
    # Check if bash menu script exists
    bash_menu_path = Path(__file__).parent.parent / "odoo-manager-menu"

    while True:
        console.clear()
        console.print()

        # Header
        header = Panel(
            "[bold cyan]Odoo Manager[/bold cyan] [dim]v{version}[/dim]\n\n"
            "A local Odoo instance management tool similar to odoo.sh".format(version=__version__),
            border_style="cyan",
            padding=(1, 2),
        )
        console.print(header)
        console.print()

        # Main menu
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="dim")
        table.add_column("", style="yellow")

        table.add_row("[1]", "Instances", "Manage Odoo instances")
        table.add_row("[2]", "Databases", "Manage databases")
        table.add_row("[3]", "Modules", "Install/Update/Uninstall modules")
        table.add_row("[4]", "Backups", "Backup & Restore")
        table.add_row("[5]", "Logs", "View logs")
        table.add_row("[6]", "Git", "Git repository management")
        table.add_row("[7]", "Environments", "Multi-environment management")
        table.add_row("[8]", "Deploy", "CI/CD deployment")
        table.add_row("[9]", "Monitor", "Health monitoring")
        table.add_row("[10]", "Scheduler", "Scheduled tasks")
        table.add_row("[11]", "SSH", "SSH access")
        table.add_row("[12]", "Users", "User management")
        table.add_row("[13]", "SSL", "SSL/TLS certificates")
        table.add_row("[14]", "Config", "Configuration")
        table.add_row("[15]", "Shell", "Odoo Python shell")
        table.add_row("[T]", "Terminal UI", "Panel-style interface")
        table.add_row("[Q]", "Quit", "Exit Odoo Manager")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select an option[/bold cyan] [dim](1-15, T, Q)[/dim]: ").strip().upper()

        if choice == "Q":
            console.print("[yellow]Goodbye![/yellow]")
            break
        elif choice == "T":
            # Launch TUI
            console.print("[dim]Launching Terminal UI...[/dim]\n")
            try:
                from odoo_manager.tui.app import OdooManagerApp
                app = OdooManagerApp()
                app.run()
            except ImportError:
                console.print("[yellow]TUI not available. Please install textual:[/yellow]")
                console.print("  pip install --break-system-packages textual")
            except Exception as e:
                console.print(f"[red]Error launching TUI: {e}[/red]")
            input("\nPress Enter to continue...")
        elif choice == "1":
            show_instance_menu()
        elif choice == "2":
            show_db_menu()
        elif choice == "3":
            show_module_menu()
        elif choice == "4":
            show_backup_menu()
        elif choice == "5":
            show_logs_menu()
        elif choice == "6":
            show_git_menu()
        elif choice == "7":
            show_environment_menu()
        elif choice == "8":
            show_deploy_menu()
        elif choice == "9":
            show_monitor_menu()
        elif choice == "10":
            show_scheduler_menu()
        elif choice == "11":
            show_ssh_menu()
        elif choice == "12":
            show_user_menu()
        elif choice == "13":
            show_ssl_menu()
        elif choice == "14":
            show_config_menu()
        elif choice == "15":
            show_shell_menu()
        else:
            console.print(f"[red]Invalid option: {choice}[/red]")
            input("Press Enter to continue...")


def execute_command(cmd: list):
    """Execute a command and return to menu."""
    console.print(f"\n[dim]Executing: {' '.join(cmd)}[/dim]\n")
    result = subprocess.run(cmd, shell=False, stdin=subprocess.DEVNULL)
    input("\nPress Enter to continue...")


def show_instance_menu():
    """Show instance management menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]Instance Management[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "List all instances")
        table.add_row("[2]", "Create new instance")
        table.add_row("[3]", "Start instance")
        table.add_row("[4]", "Stop instance")
        table.add_row("[5]", "Restart instance")
        table.add_row("[6]", "Show instance status")
        table.add_row("[7]", "Show instance info")
        table.add_row("[8]", "Remove instance")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            execute_command(["odoo-manager", "instance", "list"])
        elif choice == "2":
            name = console.input("Instance name: ")
            version = console.input("Version [default: master]: ") or "master"
            edition = console.input("Edition [community/enterprise, default: community]: ") or "community"
            port = console.input("Port [default: 8069]: ") or "8069"
            workers = console.input("Workers [default: 4]: ") or "4"
            execute_command(["odoo-manager", "instance", "create", name,
                          "--version", version, "--edition", edition,
                          "--port", port, "--workers", workers])
        elif choice == "3":
            name = console.input("Instance name: ")
            execute_command(["odoo-manager", "instance", "start", name])
        elif choice == "4":
            name = console.input("Instance name: ")
            execute_command(["odoo-manager", "instance", "stop", name])
        elif choice == "5":
            name = console.input("Instance name: ")
            execute_command(["odoo-manager", "instance", "restart", name])
        elif choice == "6":
            name = console.input("Instance name: ")
            execute_command(["odoo-manager", "instance", "status", name])
        elif choice == "7":
            name = console.input("Instance name: ")
            execute_command(["odoo-manager", "instance", "info", name])
        elif choice == "8":
            name = console.input("Instance name: ")
            confirm = console.input(f"Remove instance '{name}'? (yes/no): ")
            if confirm.lower() == "yes":
                execute_command(["odoo-manager", "instance", "rm", name, "--force"])


def show_db_menu():
    """Show database menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]Database Management[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "List databases")
        table.add_row("[2]", "Create database")
        table.add_row("[3]", "Drop database")
        table.add_row("[4]", "Backup database")
        table.add_row("[5]", "Restore database")
        table.add_row("[6]", "Duplicate database")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            instance = console.input("Instance name: ")
            execute_command(["odoo-manager", "db", "list", "--instance", instance])
        elif choice == "2":
            instance = console.input("Instance name: ")
            name = console.input("Database name: ")
            execute_command(["odoo-manager", "db", "create", name, "--instance", instance])
        elif choice == "3":
            instance = console.input("Instance name: ")
            name = console.input("Database name: ")
            execute_command(["odoo-manager", "db", "drop", name, "--instance", instance])


def show_module_menu():
    """Show module menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]Module Management[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "List modules")
        table.add_row("[2]", "Install module")
        table.add_row("[3]", "Uninstall module")
        table.add_row("[4]", "Update module")
        table.add_row("[5]", "Update all modules")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            instance = console.input("Instance name: ")
            execute_command(["odoo-manager", "module", "list", "--instance", instance])
        elif choice == "2":
            instance = console.input("Instance name: ")
            module = console.input("Module name: ")
            execute_command(["odoo-manager", "module", "install", module, "--instance", instance])


def show_backup_menu():
    """Show backup menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]Backup Management[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "List backups")
        table.add_row("[2]", "Create backup")
        table.add_row("[3]", "Restore backup")
        table.add_row("[4]", "Delete backup")
        table.add_row("[5]", "Cleanup old backups")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            execute_command(["odoo-manager", "backup", "list"])
        elif choice == "2":
            instance = console.input("Instance name: ")
            execute_command(["odoo-manager", "backup", "create", instance])


def show_logs_menu():
    """Show logs menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]Log Viewing[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "Show logs")
        table.add_row("[2]", "Follow logs (live)")
        table.add_row("[3]", "Show last N lines")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            instance = console.input("Instance name: ")
            execute_command(["odoo-manager", "logs", "show", instance])
        elif choice == "2":
            instance = console.input("Instance name: ")
            console.print("[dim]Press Ctrl+C to stop following...[/dim]")
            execute_command(["odoo-manager", "logs", "show", instance, "--follow"])


def show_git_menu():
    """Show git menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]Git Management[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "List repositories")
        table.add_row("[2]", "Clone repository")
        table.add_row("[3]", "Show branches")
        table.add_row("[4]", "Checkout branch")
        table.add_row("[5]", "Pull changes")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            execute_command(["odoo-manager", "git", "list"])
        elif choice == "2":
            url = console.input("Repository URL: ")
            execute_command(["odoo-manager", "git", "clone", url])


def show_environment_menu():
    """Show environment menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]Environment Management[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "List environments")
        table.add_row("[2]", "Create environment")
        table.add_row("[3]", "Deploy to environment")
        table.add_row("[4]", "Promote environment")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            execute_command(["odoo-manager", "env", "list"])


def show_deploy_menu():
    """Show deploy menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]CI/CD Deployment[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "Deploy branch")
        table.add_row("[2]", "Validate deployment")
        table.add_row("[3]", "Rollback deployment")
        table.add_row("[4]", "Show deployment history")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            branch = console.input("Branch name: ")
            env = console.input("Environment: ")
            execute_command(["odoo-manager", "deploy", branch, "--environment", env])


def show_monitor_menu():
    """Show monitor menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]Health Monitoring[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "Show all status")
        table.add_row("[2]", "Check instance health")
        table.add_row("[3]", "Show resource usage")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            execute_command(["odoo-manager", "monitor", "status"])


def show_scheduler_menu():
    """Show scheduler menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]Task Scheduler[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "Start scheduler")
        table.add_row("[2]", "Stop scheduler")
        table.add_row("[3]", "Show scheduler status")
        table.add_row("[4]", "List scheduled tasks")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            execute_command(["odoo-manager", "scheduler", "start"])
        elif choice == "2":
            execute_command(["odoo-manager", "scheduler", "stop"])
        elif choice == "3":
            execute_command(["odoo-manager", "scheduler", "status"])


def show_ssh_menu():
    """Show SSH menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]SSH Access[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "Open SSH shell")
        table.add_row("[2]", "Execute command")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            instance = console.input("Instance name: ")
            console.print("[dim]Press Ctrl+D to exit...[/dim]")
            os.system(f"odoo-manager ssh {instance}")


def show_user_menu():
    """Show user menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]User Management[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "List users")
        table.add_row("[2]", "Add user")
        table.add_row("[3]", "Remove user")
        table.add_row("[4]", "Set user permissions")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            execute_command(["odoo-manager", "user", "list"])


def show_ssl_menu():
    """Show SSL menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]SSL/TLS Management[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "Generate self-signed certificate")
        table.add_row("[2]", "Setup Let's Encrypt")
        table.add_row("[3]", "Show certificate status")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            domain = console.input("Domain name: ")
            execute_command(["odoo-manager", "ssl", "generate", domain])


def show_config_menu():
    """Show config menu."""
    while True:
        console.clear()
        console.print()
        header = Panel("[bold cyan]Configuration[/bold cyan]", border_style="cyan", padding=(0, 2))
        console.print(header)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="cyan")
        table.add_column("", style="white")

        table.add_row("[1]", "Show configuration")
        table.add_row("[2]", "Show config file path")
        table.add_row("[3]", "Initialize configuration")
        table.add_row("[4]", "Set configuration value")
        table.add_row("[B]", "Back to main menu")

        console.print(table)
        console.print()

        choice = console.input("[bold cyan]Select option[/bold cyan]: ").strip().upper()

        if choice == "B":
            break
        elif choice == "1":
            execute_command(["odoo-manager", "config", "show"])
        elif choice == "3":
            execute_command(["odoo-manager", "config", "init"])


def show_shell_menu():
    """Show shell menu."""
    console.clear()
    console.print()

    instance = console.input("Instance name: ")
    db = console.input("Database name [optional]: ")

    console.print("[dim]Starting Odoo shell. Press Ctrl+D to exit...[/dim]\n")

    cmd = ["odoo-manager", "shell", instance]
    if db:
        cmd.extend(["--database", db])

    os.system(" ".join(cmd))
    input("\nPress Enter to continue...")


@click.group(invoke_without_command=True)
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

    Run without arguments to enter interactive menu mode.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = Path(config)
    ctx.obj["verbose"] = verbose
    ctx.obj["json"] = json

    # If no subcommand provided, show interactive menu
    if ctx.invoked_subcommand is None:
        show_interactive_menu()


@main.command()
def version():
    """Show version information."""
    console.print(f"Odoo Manager version [cyan]{__version__}[/cyan]")


@main.command()
def menu():
    """Launch the interactive menu."""
    show_interactive_menu()


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
