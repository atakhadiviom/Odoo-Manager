"""
Simplified Terminal UI for Odoo Manager.

Simple numbered menu interface like a bash script.
"""

import os
import subprocess
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from odoo_manager.instance import Instance, InstanceManager
from odoo_manager.git import GitManager
from odoo_manager.module import ModuleManager
from odoo_manager.database import DatabaseManager
from odoo_manager.utils.docker import ensure_docker

console = Console()


class SimpleTUI:
    """Simple TUI with numbered menus."""

    def __init__(self):
        self.running = True
        self.manager = InstanceManager()

    def run(self):
        """Run the TUI."""
        console.clear()
        self.show_main_menu()

    def show_main_menu(self):
        """Show main menu."""
        while self.running:
            console.clear()
            console.print(
                Panel(
                    """[bold cyan]Odoo Manager[/bold cyan] [dim]v0.2.0[/dim]

[bold]Main Menu[/bold]

  [1]  [cyan]Instances[/cyan]    Manage Odoo instances
  [2]  [cyan]Git[/cyan]          Connect repository & auto-deploy
  [3]  [cyan]Modules[/cyan]      Install/uninstall modules
  [4]  [cyan]Database[/cyan]     Backup & restore databases
  [5]  [cyan]Logs[/cyan]         View instance logs

  [0]  [dim]Quit[/dim]""",
                    title="Odoo.sh Manager",
                    border_style="cyan"
                )
            )

            choice = input("\nSelect option (0-5): ").strip()

            if choice == "0" or choice.lower() == "q":
                console.print("[yellow]Goodbye![/yellow]")
                self.running = False
                return
            elif choice == "1":
                self.show_instances()
            elif choice == "2":
                self.show_git_menu()
            elif choice == "3":
                self.show_modules_menu()
            elif choice == "4":
                self.show_database_menu()
            elif choice == "5":
                self.show_logs_menu()

    def show_instances(self):
        """Show instances menu."""
        while True:
            console.clear()

            instances = self.manager.list_instances()

            if not instances:
                console.print(Panel("[yellow]No instances found.[/yellow]", border_style="yellow"))
            else:
                table = Table(title="Odoo Instances", show_header=True, header_style="bold cyan")
                table.add_column("#", style="dim", width=3)
                table.add_column("Name", style="cyan")
                table.add_column("Version", width=8)
                table.add_column("Environment", width=12)
                table.add_column("Port", width=6)
                table.add_column("Status", width=10)

                for i, inst in enumerate(instances, 1):
                    status = "[green]RUNNING[/green]" if inst.is_running() else "[red]STOPPED[/red]"
                    env = inst.config.environment or "dev"
                    table.add_row(str(i), inst.config.name, inst.config.version, env, str(inst.config.port), status)

                console.print(table)

            console.print("\n  [C]  Create New Instance")
            console.print("  [0]  Back to main menu")

            choice = input("\nSelect option: ").strip().lower()

            if choice == "0":
                return
            elif choice == "c":
                self.create_instance()
            elif choice.isdigit() and 1 <= int(choice) <= len(instances):
                inst = instances[int(choice) - 1]
                self.show_instance_actions(inst)

    def show_instance_actions(self, instance: Instance):
        """Show actions for an instance."""
        while True:
            console.clear()

            status_color = "green" if instance.is_running() else "red"
            status = "RUNNING" if instance.is_running() else "STOPPED"

            table = Table(title=f"Instance: {instance.config.name}", show_header=False)
            table.add_column("Property", style="cyan")
            table.add_column("Value")

            table.add_row("Status", f"[{status_color}]{status}[/{status_color}]")
            table.add_row("Version", instance.config.version)
            table.add_row("Environment", instance.config.environment or "dev")
            table.add_row("Port", f":{instance.config.port}")
            if instance.config.git_repo:
                table.add_row("Git Repo", instance.config.git_repo)

            console.print(table)

            console.print("\n[bold]Actions[/bold]")
            console.print("  [1]  Start          Start the instance")
            console.print("  [2]  Stop           Stop the instance")
            console.print("  [3]  Restart        Restart the instance")
            console.print("  [4]  Logs           View logs")
            console.print("  [5]  Shell          Open Odoo shell")
            console.print("  [6]  Remove         Delete instance")
            console.print("\n  [0]  Back")

            choice = input(f"\nSelect action: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                self.do_start(instance)
            elif choice == "2":
                self.do_stop(instance)
            elif choice == "3":
                self.do_restart(instance)
            elif choice == "4":
                self.view_logs(instance)
            elif choice == "5":
                self.open_shell(instance)
            elif choice == "6":
                if input(f"Remove '{instance.config.name}'? (yes/no): ").strip().lower() == "yes":
                    self.do_remove(instance)
                    return

    def create_instance(self):
        """Create a new instance."""
        console.clear()

        # Name
        console.print(Panel("[bold cyan]Create New Instance[/bold cyan]", border_style="cyan"))
        name = input("\nEnter instance name: ").strip()
        if not name:
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        # Version
        console.print("\n[bold]Select Version:[/bold]")
        console.print("  [1]  19.0 (Latest)")
        console.print("  [2]  18.0")
        console.print("  [3]  17.0")
        version_choice = input("\nSelect version (1-3): ").strip()
        versions = {"1": "19.0", "2": "18.0", "3": "17.0"}
        version = versions.get(version_choice, "19.0")

        # Environment
        console.print("\n[bold]Select Environment:[/bold]")
        console.print("  [1]  Development    - Fresh DB with demo data")
        console.print("  [2]  Staging        - Copy from production database")
        console.print("  [3]  Production     - Fresh database, no demo data")
        env_choice = input("\nSelect environment (1-3): ").strip()
        environments = {"1": Instance.ENV_DEV, "2": Instance.ENV_STAGING, "3": Instance.ENV_PRODUCTION}
        environment = environments.get(env_choice, Instance.ENV_DEV)

        # For staging, ask for source instance
        source_instance_name = None
        if environment == Instance.ENV_STAGING:
            console.print("\n[bold]Select Production Instance to Copy:[/bold]")
            prod_instances = [i for i in self.manager.list_instances()
                             if i.config.environment == Instance.ENV_PRODUCTION]

            if not prod_instances:
                console.print("[yellow]No production instances found. Creating with fresh database.[/yellow]")
            else:
                for i, inst in enumerate(prod_instances, 1):
                    console.print(f"  [{i}]  {inst.config.name}")
                console.print("  [0]  Fresh database (no copy)")

                source_choice = input("\nSelect source instance: ").strip()
                if source_choice != "0" and source_choice.isdigit() and 1 <= int(source_choice) <= len(prod_instances):
                    source_instance_name = prod_instances[int(source_choice) - 1].config.name
                    console.print(f"[cyan]Will copy database from: {source_instance_name}[/cyan]")

        # Port
        port = input(f"\nEnter port (default 8069): ").strip()
        port = int(port) if port else 8069

        # Git repo (optional)
        git_repo = input("\nGit repository URL (optional, press Enter to skip): ").strip() or None

        # Summary
        source_info = f"Source DB: {source_instance_name}" if source_instance_name else "Source DB: Fresh database"
        console.print(Panel(
            f"""[bold]Summary[/bold]

  Name:         [cyan]{name}[/cyan]
  Version:      [cyan]{version}[/cyan]
  Environment:  [cyan]{environment}[/cyan]
  {source_info}
  Port:         [cyan]{port}[/cyan]
  Git Repo:     [cyan]{git_repo or 'None'}[/cyan]

  [1]  Create
  [0]  Cancel""",
            border_style="cyan"
        ))

        confirm = input("\nConfirm? (1=Create, 0=Cancel): ").strip()
        if confirm != "1":
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        # Ensure Docker is installed
        console.print("\n[dim]Checking Docker...[/dim]")
        success, message = ensure_docker(verbose=True)
        if not success:
            console.print(f"[red]{message}[/red]")
            input("\nPress Enter to continue...")
            return

        # Create instance
        console.print("[dim]Creating instance...[/dim]")
        try:
            instance = self.manager.create_instance(
                name=name,
                version=version,
                port=port,
                environment=environment,
                git_repo=git_repo,
            )
            console.print(f"[green]Instance '{name}' created![/green]")

            # Clone git repo if provided
            if git_repo:
                console.print(f"[dim]Cloning repository...[/dim]")
                git_mgr = GitManager(instance)
                git_mgr.clone_repo(git_repo)
                console.print(f"[green]Repository cloned![/green]")

            # For staging, copy database from source
            if environment == Instance.ENV_STAGING and source_instance_name:
                console.print(f"[dim]Copying database from {source_instance_name}...[/dim]")
                from odoo_manager.database import DatabaseManager
                source_inst = self.manager.get_instance(source_instance_name)
                if source_inst:
                    db_mgr = DatabaseManager(source_inst)
                    # Backup source database
                    backup_path = db_mgr.backup()
                    # Restore to new instance
                    target_db_mgr = DatabaseManager(instance)
                    target_db_mgr.restore(backup_path, instance.config.db_name)
                    console.print(f"[green]Database copied![/green]")

            # Start instance
            console.print(f"[dim]Starting instance...[/dim]")
            instance.start()
            console.print(f"[green]Instance '{name}' started![/green]")
            console.print(f"\n[cyan]Access at: http://localhost:{port}[/cyan]")

            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    def show_git_menu(self):
        """Show Git management menu."""
        console.clear()
        console.print(Panel("[bold cyan]Git Repository Management[/bold cyan]", border_style="cyan"))

        instances = self.manager.list_instances()
        if not instances:
            console.print("[yellow]No instances found. Create an instance first.[/yellow]")
            input("\nPress Enter to continue...")
            return

        console.print("\n[bold]Select Instance:[/bold]")
        for i, inst in enumerate(instances, 1):
            repo_info = inst.config.git_repo or "No repo"
            console.print(f"  [{i}]  {inst.config.name} - {repo_info}")
        console.print("\n  [0]  Back")

        choice = input("\nSelect instance: ").strip()
        if choice == "0":
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(instances):
            inst = instances[int(choice) - 1]
            self.show_instance_git(inst)

    def show_instance_git(self, instance: Instance):
        """Show Git operations for an instance."""
        while True:
            console.clear()
            console.print(Panel(f"[bold cyan]Git: {instance.config.name}[/bold cyan]", border_style="cyan"))

            git_mgr = GitManager(instance)

            try:
                branch = git_mgr.get_current_branch()
                commit = git_mgr.get_current_commit()
                console.print(f"  Branch:  [cyan]{branch}[/cyan]")
                console.print(f"  Commit:  [dim]{commit}[/dim]")
            except Exception:
                console.print("  [yellow]No Git repository found[/yellow]")

            console.print("\n[bold]Actions[/bold]")
            console.print("  [1]  Pull Latest    Pull latest changes from repo")
            console.print("  [2]  Restart        Restart instance after changes")
            console.print("  [3]  List Modules   List available modules")
            console.print("\n  [0]  Back")

            choice = input("\nSelect action: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                try:
                    console.print("\n[dim]Pulling latest changes...[/dim]")
                    result = git_mgr.pull_latest()
                    console.print(f"[green]{result}[/green]")
                except Exception as e:
                    console.print(f"[red]{e}[/red]")
                input("\nPress Enter to continue...")
            elif choice == "2":
                try:
                    console.print("\n[dim]Restarting instance...[/dim]")
                    instance.restart()
                    console.print("[green]Restarted![/green]")
                except Exception as e:
                    console.print(f"[red]{e}[/red]")
                input("\nPress Enter to continue...")
            elif choice == "3":
                try:
                    modules = git_mgr.list_modules()
                    console.print(f"\n[dim]Found {len(modules)} modules[/dim]")
                    for m in modules[:20]:
                        console.print(f"  - {m}")
                    if len(modules) > 20:
                        console.print(f"  ... and {len(modules) - 20} more")
                except Exception as e:
                    console.print(f"[red]{e}[/red]")
                input("\nPress Enter to continue...")

    def show_modules_menu(self):
        """Show modules menu."""
        console.clear()
        console.print(Panel("[bold cyan]Module Management[/bold cyan]", border_style="cyan"))

        instances = [i for i in self.manager.list_instances() if i.is_running()]
        if not instances:
            console.print("[yellow]No running instances found.[/yellow]")
            input("\nPress Enter to continue...")
            return

        console.print("\n[bold]Select Instance:[/bold]")
        for i, inst in enumerate(instances, 1):
            console.print(f"  [{i}]  {inst.config.name}")
        console.print("\n  [0]  Back")

        choice = input("\nSelect instance: ").strip()
        if choice == "0":
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(instances):
            inst = instances[int(choice) - 1]
            self.show_instance_modules(inst)

    def show_instance_modules(self, instance: Instance):
        """Show modules for an instance."""
        mod_mgr = ModuleManager(instance)

        while True:
            console.clear()
            console.print(Panel(f"[bold cyan]Modules: {instance.config.name}[/bold cyan]", border_style="cyan"))

            try:
                modules = mod_mgr.list_modules()
                console.print(f"\n[dim]Showing first 20 of {len(modules)} modules[/dim]\n")

                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Module", style="cyan")
                table.add_column("State", width=12)

                for m in modules[:20]:
                    state_color = "green" if m["state"] == "installed" else "yellow"
                    table.add_row(m["name"], f"[{state_color}]{m['state']}[/{state_color}]")

                console.print(table)
            except Exception as e:
                console.print(f"[red]Error listing modules: {e}[/red]")

            console.print("\n[bold]Actions[/bold]")
            console.print("  [1]  Install        Install modules (comma-separated)")
            console.print("  [2]  Uninstall      Uninstall modules")
            console.print("  [3]  Update         Update modules")
            console.print("\n  [0]  Back")

            choice = input("\nSelect action: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                mods = input("\nEnter module names (comma-separated): ").strip()
                if mods:
                    module_list = [m.strip() for m in mods.split(",")]
                    console.print(f"\n[dim]Installing: {', '.join(module_list)}[/dim]")
                    try:
                        result = mod_mgr.install(module_list)
                        console.print("[green]Done![/green]")
                        console.print(result[:500])
                    except Exception as e:
                        console.print(f"[red]{e}[/red]")
                    input("\nPress Enter to continue...")
            elif choice == "2":
                mods = input("\nEnter module names (comma-separated): ").strip()
                if mods:
                    module_list = [m.strip() for m in mods.split(",")]
                    console.print(f"\n[dim]Uninstalling: {', '.join(module_list)}[/dim]")
                    try:
                        result = mod_mgr.uninstall(module_list)
                        console.print("[green]Done![/green]")
                    except Exception as e:
                        console.print(f"[red]{e}[/red]")
                    input("\nPress Enter to continue...")
            elif choice == "3":
                mods = input("\nEnter module names (comma-separated, or 'all'): ").strip()
                console.print(f"\n[dim]Updating: {mods}[/dim]")
                try:
                    module_list = None if mods.lower() == "all" else [m.strip() for m in mods.split(",")]
                    result = mod_mgr.update(module_list)
                    console.print("[green]Done![/green]")
                except Exception as e:
                    console.print(f"[red]{e}[/red]")
                input("\nPress Enter to continue...")

    def show_database_menu(self):
        """Show database menu."""
        console.clear()
        console.print(Panel("[bold cyan]Database Management[/bold cyan]", border_style="cyan"))

        instances = self.manager.list_instances()
        if not instances:
            console.print("[yellow]No instances found.[/yellow]")
            input("\nPress Enter to continue...")
            return

        console.print("\n[bold]Select Instance:[/bold]")
        for i, inst in enumerate(instances, 1):
            console.print(f"  [{i}]  {inst.config.name}")
        console.print("\n  [0]  Back")

        choice = input("\nSelect instance: ").strip()
        if choice == "0":
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(instances):
            inst = instances[int(choice) - 1]
            self.show_instance_databases(inst)

    def show_instance_databases(self, instance: Instance):
        """Show databases for an instance."""
        db_mgr = DatabaseManager(instance)

        while True:
            console.clear()
            console.print(Panel(f"[bold cyan]Databases: {instance.config.name}[/bold cyan]", border_style="cyan"))

            try:
                databases = db_mgr.list_databases()
                for db in databases:
                    console.print(f"  - {db}")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

            console.print("\n[bold]Actions[/bold]")
            console.print("  [1]  Backup         Create backup")
            console.print("  [2]  Restore        Restore from backup")
            console.print("  [3]  Duplicate      Duplicate database")
            console.print("  [4]  List Backups   Show backup files")
            console.print("\n  [0]  Back")

            choice = input("\nSelect action: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                try:
                    console.print("\n[dim]Creating backup...[/dim]")
                    backup_path = db_mgr.backup()
                    console.print(f"[green]Backup saved: {backup_path}[/green]")
                except Exception as e:
                    console.print(f"[red]{e}[/red]")
                input("\nPress Enter to continue...")
            elif choice == "2":
                backups = db_mgr.list_backups()
                if not backups:
                    console.print("[yellow]No backups found[/yellow]")
                    input("\nPress Enter to continue...")
                    continue
                console.print("\nAvailable backups:")
                for i, b in enumerate(backups, 1):
                    console.print(f"  [{i}]  {b['name']}")
                choice = input("\nSelect backup: ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(backups):
                    backup = backups[int(choice) - 1]
                    try:
                        console.print("\n[dim]Restoring...[/dim]")
                        db_mgr.restore(Path(backup['path']))
                        console.print("[green]Restored![/green]")
                    except Exception as e:
                        console.print(f"[red]{e}[/red]")
                input("\nPress Enter to continue...")
            elif choice == "3":
                db_name = input("\nNew database name: ").strip()
                if db_name:
                    try:
                        console.print(f"\n[dim]Duplicating to {db_name}...[/dim]")
                        db_mgr.duplicate(instance.config.db_name, db_name)
                        console.print("[green]Done![/green]")
                    except Exception as e:
                        console.print(f"[red]{e}[/red]")
                input("\nPress Enter to continue...")
            elif choice == "4":
                backups = db_mgr.list_backups()
                if backups:
                    console.print("\n[dim]Backup files:[/dim]")
                    for b in backups:
                        console.print(f"  - {b['name']} ({b['size']} bytes)")
                else:
                    console.print("[yellow]No backups found[/yellow]")
                input("\nPress Enter to continue...")

    def show_logs_menu(self):
        """Show logs menu."""
        console.clear()
        console.print(Panel("[bold cyan]View Logs[/bold cyan]", border_style="cyan"))

        instances = self.manager.list_instances()
        if not instances:
            console.print("[yellow]No instances found.[/yellow]")
            input("\nPress Enter to continue...")
            return

        console.print("\n[bold]Select Instance:[/bold]")
        for i, inst in enumerate(instances, 1):
            status = "[green]Running[/green]" if inst.is_running() else "[red]Stopped[/red]"
            console.print(f"  [{i}]  {inst.config.name} {status}")
        console.print("\n  [0]  Back")

        choice = input("\nSelect instance: ").strip()
        if choice == "0":
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(instances):
            inst = instances[int(choice) - 1]
            self.view_logs(inst)

    def view_logs(self, instance: Instance):
        """View logs for an instance."""
        console.clear()
        console.print(Panel(f"[bold cyan]Logs: {instance.config.name}[/bold cyan]", border_style="cyan"))

        console.print("\n[bold]Options[/bold]")
        console.print("  [1]  Last 100 lines")
        console.print("  [2]  Last 500 lines")
        console.print("  [3]  Follow mode (live)")
        console.print("\n  [0]  Back")

        choice = input("\nSelect option: ").strip()

        if choice == "0":
            return
        elif choice == "1":
            logs = instance.get_logs(tail=100)
            console.print(f"\n{logs}")
            input("\nPress Enter to continue...")
        elif choice == "2":
            logs = instance.get_logs(tail=500)
            console.print(f"\n{logs[:2000]}")  # Limit output
            input("\nPress Enter to continue...")
        elif choice == "3":
            console.print("\n[dim]Following logs... (Press Ctrl+C to stop)[/dim]\n")
            try:
                instance.get_logs(follow=True)
            except KeyboardInterrupt:
                console.print("\n\n[yellow]Log following stopped[/yellow]")
                input("\nPress Enter to continue...")

    # ===== Instance Actions =====
    def do_start(self, instance: Instance):
        """Start an instance."""
        console.print(f"\n[dim]Starting {instance.config.name}...[/dim]")
        try:
            instance.start()
            console.print(f"[green]Started![/green]")
        except Exception as e:
            console.print(f"[red]{e}[/red]")
        input("\nPress Enter to continue...")

    def do_stop(self, instance: Instance):
        """Stop an instance."""
        console.print(f"\n[dim]Stopping {instance.config.name}...[/dim]")
        try:
            instance.stop()
            console.print(f"[yellow]Stopped![/yellow]")
        except Exception as e:
            console.print(f"[red]{e}[/red]")
        input("\nPress Enter to continue...")

    def do_restart(self, instance: Instance):
        """Restart an instance."""
        console.print(f"\n[dim]Restarting {instance.config.name}...[/dim]")
        try:
            instance.restart()
            console.print(f"[yellow]Restarted![/yellow]")
        except Exception as e:
            console.print(f"[red]{e}[/red]")
        input("\nPress Enter to continue...")

    def do_remove(self, instance: Instance):
        """Remove an instance."""
        console.print(f"\n[dim]Removing {instance.config.name}...[/dim]")
        try:
            instance.remove()
            self.manager.remove_instance(instance.config.name)
            console.print(f"[red]Removed![/red]")
        except Exception as e:
            console.print(f"[red]{e}[/red]")
        input("\nPress Enter to continue...")

    def open_shell(self, instance: Instance):
        """Open Odoo Python shell."""
        if not instance.is_running():
            console.print("[yellow]Instance must be running first[/yellow]")
            input("\nPress Enter to continue...")
            return

        console.print(f"\n[dim]Opening shell for {instance.config.name}...[/dim]")
        console.print("[dim]Press Ctrl+D to exit[/dim]\n")

        docker_cmd = instance._get_docker_cmd()
        cmd = docker_cmd + ["exec", "-it", instance.container_name, "odoo-bin", "shell"]
        subprocess.run(cmd)


def launch_tui():
    """Launch the TUI."""
    app = SimpleTUI()
    app.run()
