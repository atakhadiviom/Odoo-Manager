"""
Terminal UI for Odoo Manager - Complete with all features.

Simple numbered menu like a bash script.
"""

import sys
import subprocess
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from odoo_manager.core.instance import InstanceManager
from odoo_manager.core.database import DatabaseManager
from odoo_manager.core.module import ModuleManager
from odoo_manager.core.backup import BackupManager
from odoo_manager.core.monitor import HealthMonitor


console = Console()


class SimpleTUI:
    """Simple TUI with numbered menus."""

    def __init__(self):
        self.running = True

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
                    """[bold cyan]Odoo Manager[/bold cyan] [dim]v0.1.0[/dim]

A complete Odoo instance management tool

[bold]Main Menu[/bold]

  [1]  Instances       Manage Odoo instances
  [2]  Databases       Manage databases
  [3]  Modules         Install/Update modules
  [4]  Backups         Backup & Restore
  [5]  Logs            View logs
  [6]  Monitor         Health monitoring
  [7]  Config          Configuration
  [8]  Shell           Odoo Python shell

  [0]  [dim]Quit[/dim]""",
                    title="📦 Odoo Manager",
                    border_style="cyan"
                )
            )

            choice = input("\nSelect option (0-8): ").strip()

            if choice == "0" or choice.lower() == "q":
                console.print("[yellow]Goodbye![/yellow]")
                self.running = False
                return
            elif choice == "1":
                self.show_instances()
            elif choice == "2":
                self.show_databases()
            elif choice == "3":
                self.show_modules()
            elif choice == "4":
                self.show_backups()
            elif choice == "5":
                self.show_logs()
            elif choice == "6":
                self.show_monitor()
            elif choice == "7":
                self.show_config()
            elif choice == "8":
                self.show_shell()

    def show_instances(self):
        """Show instances menu."""
        while True:
            try:
                manager = InstanceManager()
                instances = manager.list_instances()
                monitor = HealthMonitor()

                instance_list = []
                for inst in instances:
                    health = monitor.check_instance(inst)
                    instance_list.append({
                        "name": inst.config.name,
                        "version": inst.config.version,
                        "status": inst.status(),
                        "running": inst.is_running(),
                        "port": inst.config.port,
                        "cpu": health.cpu_percent,
                        "memory": health.memory_percent,
                    })
            except:
                instance_list = []

            console.clear()

            # Build table
            table = Table(title="Odoo Instances", show_header=True, header_style="bold cyan")
            table.add_column("#", style="dim", width=3)
            table.add_column("Name", style="cyan")
            table.add_column("Status", width=10)
            table.add_column("Version", width=8)
            table.add_column("Port", width=6)
            table.add_column("CPU", width=8)
            table.add_column("Memory", width=8)

            if not instance_list:
                console.print(Panel("[yellow]No instances found.[/yellow]", border_style="yellow"))
            else:
                for i, inst in enumerate(instance_list, 1):
                    status = "[green]RUNNING[/green]" if inst["running"] else "[red]STOPPED[/red]"
                    cpu = f"{inst['cpu']:.1f}%" if inst['cpu'] > 0 else "N/A"
                    mem = f"{inst['memory']:.1f}%" if inst['memory'] > 0 else "N/A"
                    table.add_row(str(i), inst['name'], status, inst['version'], str(inst['port']), cpu, mem)

                console.print(table)

            console.print("\n  [C]  Create New Instance")
            console.print("  [0]  Back to main menu")

            choice = input("\nSelect option: ").strip().lower()

            if choice == "0":
                return
            elif choice == "c":
                self.create_instance()
            elif choice.isdigit() and 1 <= int(choice) <= len(instance_list):
                inst = instance_list[int(choice) - 1]
                self.show_instance_actions(inst)

    def show_instance_actions(self, instance: dict):
        """Show actions for an instance."""
        while True:
            console.clear()

            status_color = "green" if instance["running"] else "red"

            table = Table(title=f"Instance: {instance['name']}", show_header=False)
            table.add_column("Property", style="cyan")
            table.add_column("Value")

            table.add_row("Status", f"[{status_color}]{instance['status'].upper()}[/{status_color}]")
            table.add_row("Version", instance['version'])
            table.add_row("Port", f":{instance['port']}")
            if instance.get('cpu', 0) > 0:
                table.add_row("CPU", f"{instance['cpu']:.1f}%")
            if instance.get('memory', 0) > 0:
                table.add_row("Memory", f"{instance['memory']:.1f}%")

            console.print(table)

            console.print("\n[bold]Actions[/bold]")
            console.print("  [1]  Start          Start the instance")
            console.print("  [2]  Stop           Stop the instance")
            console.print("  [3]  Restart        Restart the instance")
            console.print("  [4]  Logs           View logs")
            console.print("  [5]  Shell          Open Python shell")
            console.print("  [6]  Remove         Delete instance")
            console.print("\n  [0]  Back")

            choice = input(f"\nSelect action for {instance['name']}: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                self.do_instance_action(instance["name"], "start")
                if instance.get("running") == False:
                    # Status changed, refresh
                    return
            elif choice == "2":
                self.do_instance_action(instance["name"], "stop")
                if instance.get("running") == True:
                    return
            elif choice == "3":
                self.do_instance_action(instance["name"], "restart")
            elif choice == "4":
                self.view_logs(instance["name"])
            elif choice == "5":
                self.open_shell(instance["name"])
            elif choice == "6":
                if input(f"Remove '{instance['name']}'? (yes/no): ").strip().lower() == "yes":
                    self.do_instance_action(instance["name"], "remove")
                    return

    def show_databases(self):
        """Show databases menu."""
        # First select an instance
        instances = self.get_instances_list()
        if not instances:
            console.print(Panel("[yellow]No instances found.[/yellow] Create an instance first.", border_style="yellow"))
            input("\nPress Enter to continue...")
            return

        console.clear()
        console.print(Panel("[bold cyan]Select Instance[/bold cyan]", border_style="cyan"))
        for i, inst in enumerate(instances, 1):
            console.print(f"  [{i}]  {inst['name']}")
        console.print("\n  [0]  Back")

        choice = input("\nSelect instance: ").strip()
        if choice == "0":
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(instances):
            inst_name = instances[int(choice) - 1]["name"]
            self.show_instance_databases(inst_name)

    def show_instance_databases(self, instance_name: str):
        """Show databases for an instance."""
        while True:
            console.clear()
            console.print(Panel(f"[bold cyan]Databases: {instance_name}[/bold cyan]", border_style="cyan"))

            try:
                manager = InstanceManager()
                instance = manager.get_instance(instance_name)
                db_manager = DatabaseManager(instance)

                databases = db_manager.list_databases()

                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Database", style="cyan")
                table.add_column("Size")
                table.add_column("Owner")

                for db in databases:
                    table.add_row(db, "N/A", "odoo")

                console.print(table)

            except Exception as e:
                console.print(f"[red]Error listing databases: {e}[/red]")

            console.print("\n[bold]Actions[/bold]")
            console.print("  [1]  Create         New database")
            console.print("  [2]  Drop           Delete database")
            console.print("  [3]  Backup         Backup database")
            console.print("  [4]  Restore        Restore from backup")
            console.print("  [5]  Duplicate      Clone database")
            console.print("\n  [0]  Back")

            choice = input("\nSelect action: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                self.create_database(instance_name)
            elif choice == "2":
                self.drop_database(instance_name)
            elif choice == "3":
                self.backup_database(instance_name)
            elif choice == "4":
                self.restore_database(instance_name)
            elif choice == "5":
                self.duplicate_database(instance_name)

    def show_modules(self):
        """Show modules menu."""
        instances = self.get_instances_list()
        if not instances:
            console.print(Panel("[yellow]No instances found.[/yellow] Create an instance first.", border_style="yellow"))
            input("\nPress Enter to continue...")
            return

        console.clear()
        console.print(Panel("[bold cyan]Select Instance[/bold cyan]", border_style="cyan"))
        for i, inst in enumerate(instances, 1):
            console.print(f"  [{i}]  {inst['name']}")
        console.print("\n  [0]  Back")

        choice = input("\nSelect instance: ").strip()
        if choice == "0":
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(instances):
            inst_name = instances[int(choice) - 1]["name"]
            self.show_instance_modules(inst_name)

    def show_instance_modules(self, instance_name: str):
        """Show modules for an instance."""
        while True:
            console.clear()
            console.print(Panel(f"[bold cyan]Modules: {instance_name}[/bold cyan]", border_style="cyan"))

            try:
                manager = InstanceManager()
                instance = manager.get_instance(instance_name)
                mod_manager = ModuleManager(instance)

                modules = mod_manager.list_modules()

                # Filter: Installed vs Not Installed
                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Module", style="cyan")
                table.add_column("Installed", width=10)
                table.add_column("Version")
                table.add_column("State", width=10)

                for mod in modules[:20]:  # Show first 20
                    installed = "[green]Yes[/green]" if mod.get('installed', False) else "[red]No[/red]"
                    version = mod.get('version', 'N/A')
                    state = mod.get('state', 'uninstalled')
                    table.add_row(mod.get('name', 'Unknown'), installed, str(version), state)

                console.print(table)
                console.print(f"\n[dim]Showing first 20 of {len(modules)} modules[/dim]")

            except Exception as e:
                console.print(f"[red]Error listing modules: {e}[/red]")

            console.print("\n[bold]Actions[/bold]")
            console.print("  [1]  Install        Install modules")
            console.print("  [2]  Uninstall      Uninstall modules")
            console.print("  [3]  Update         Update modules")
            console.print("  [4]  Upgrade        Upgrade all modules")
            console.print("  [5]  Search         Search for a module")
            console.print("\n  [0]  Back")

            choice = input("\nSelect action: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                self.install_modules(instance_name)
            elif choice == "2":
                self.uninstall_modules(instance_name)
            elif choice == "3":
                self.update_modules(instance_name)
            elif choice == "4":
                self.upgrade_modules(instance_name)
            elif choice == "5":
                self.search_module(instance_name)

    def show_backups(self):
        """Show backups menu."""
        instances = self.get_instances_list()
        if not instances:
            console.print(Panel("[yellow]No instances found.[/yellow] Create an instance first.", border_style="yellow"))
            input("\nPress Enter to continue...")
            return

        console.clear()
        console.print(Panel("[bold cyan]Select Instance[/bold cyan]", border_style="cyan"))
        for i, inst in enumerate(instances, 1):
            console.print(f"  [{i}]  {inst['name']}")
        console.print("\n  [0]  Back")

        choice = input("\nSelect instance: ").strip()
        if choice == "0":
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(instances):
            inst_name = instances[int(choice) - 1]["name"]
            self.show_instance_backups(inst_name)

    def show_instance_backups(self, instance_name: str):
        """Show backups for an instance."""
        while True:
            console.clear()
            console.print(Panel(f"[bold cyan]Backups: {instance_name}[/bold cyan]", border_style="cyan"))

            try:
                manager = InstanceManager()
                instance = manager.get_instance(instance_name)
                backup_manager = BackupManager(instance)

                backups = backup_manager.list_backups()

                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Backup", style="cyan")
                table.add_column("Date")
                table.add_column("Size")
                table.add_column("Type")

                for backup in backups:
                    table.add_row(
                        backup.get('name', 'N/A'),
                        backup.get('date', 'N/A'),
                        backup.get('size', 'N/A'),
                        backup.get('type', 'N/A')
                    )

                console.print(table)

            except Exception as e:
                console.print(f"[red]Error listing backups: {e}[/red]")

            console.print("\n[bold]Actions[/bold]")
            console.print("  [1]  Create         Create new backup")
            console.print("  [2]  Restore        Restore from backup")
            console.print("  [3]  Schedule       Configure auto-backup")
            console.print("  [4]  Delete         Delete backup")
            console.print("\n  [0]  Back")

            choice = input("\nSelect action: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                self.create_backup(instance_name)
            elif choice == "2":
                self.restore_backup(instance_name)
            elif choice == "3":
                self.schedule_backup(instance_name)
            elif choice == "4":
                self.delete_backup(instance_name)

    def show_logs(self):
        """Show logs menu."""
        instances = self.get_instances_list()
        if not instances:
            console.print(Panel("[yellow]No instances found.[/yellow] Create an instance first.", border_style="yellow"))
            input("\nPress Enter to continue...")
            return

        console.clear()
        console.print(Panel("[bold cyan]Select Instance[/bold cyan]", border_style="cyan"))
        for i, inst in enumerate(instances, 1):
            console.print(f"  [{i}]  {inst['name']}")
        console.print("\n  [0]  Back")

        choice = input("\nSelect instance: ").strip()
        if choice == "0":
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(instances):
            inst_name = instances[int(choice) - 1]["name"]
            self.view_logs(inst_name)

    def show_monitor(self):
        """Show health monitoring dashboard."""
        console.clear()
        console.print(Panel("[bold cyan]Health Monitoring[/bold cyan]", border_style="cyan"))

        instances = self.get_instances_list()
        if not instances:
            console.print("[yellow]No instances found.[/yellow]")
            input("\nPress Enter to continue...")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Instance", style="cyan")
        table.add_column("Status", width=10)
        table.add_column("CPU", width=10)
        table.add_column("Memory", width=10)
        table.add_column("Disk", width=10)
        table.add_column("Uptime", width=15)

        for inst in instances:
            try:
                manager = InstanceManager()
                instance = manager.get_instance(inst["name"])
                monitor = HealthMonitor()
                health = monitor.check_instance(instance)

                status = "[green]RUNNING[/green]" if inst.get("running", False) else "[red]STOPPED[/red]"
                cpu = f"{health.cpu_percent:.1f}%" if health.cpu_percent > 0 else "N/A"
                mem = f"{health.memory_percent:.1f}%" if health.memory_percent > 0 else "N/A"
                disk = "N/A"
                uptime = "N/A"

                table.add_row(inst["name"], status, cpu, mem, disk, uptime)
            except Exception as e:
                table.add_row(inst["name"], "[red]ERROR[/red]", "N/A", "N/A", "N/A", "N/A")

        console.print(table)
        console.print("\n[dim]Press R to refresh, 0 to go back[/dim]")

        choice = input("\nAction: ").strip().lower()
        if choice == "0":
            return
        elif choice == "r":
            self.show_monitor()

    def show_config(self):
        """Show configuration management."""
        while True:
            console.clear()
            console.print(Panel("[bold cyan]Configuration[/bold cyan]", border_style="cyan"))

            console.print("\n[bold]Configuration Options[/bold]")
            console.print("  [1]  General        Basic settings")
            console.print("  [2]  Docker         Docker configuration")
            console.print("  [3]  Paths          File paths")
            console.print("  [4]  Defaults       Default values")
            console.print("  [5]  Environment    Environment variables")
            console.print("\n  [0]  Back")

            choice = input("\nSelect option: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                self.show_placeholder("General Configuration")
            elif choice == "2":
                self.show_placeholder("Docker Configuration")
            else:
                self.show_placeholder("Configuration")

    def show_shell(self):
        """Show shell access."""
        instances = self.get_instances_list(running_only=True)
        if not instances:
            console.print(Panel("[yellow]No running instances found.[/yellow]", border_style="yellow"))
            input("\nPress Enter to continue...")
            return

        console.clear()
        console.print(Panel("[bold cyan]Select Instance[/bold cyan]", border_style="cyan"))
        for i, inst in enumerate(instances, 1):
            console.print(f"  [{i}]  {inst['name']}")
        console.print("\n  [0]  Back")

        choice = input("\nSelect instance: ").strip()
        if choice == "0":
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(instances):
            inst_name = instances[int(choice) - 1]["name"]
            self.open_shell(inst_name)

    # ===== Instance Creation =====
    def create_instance(self):
        """Create a new instance - step by step."""
        console.clear()

        # Step 1: Name
        console.print(Panel("[bold cyan]Create New Instance[/bold cyan]\n\n[bold]Step 1: Enter Instance Name[/bold]", border_style="cyan"))
        name = input("\nEnter instance name: ").strip()
        if not name:
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        # Step 2: Version
        console.clear()
        console.print(Panel(
            f"[bold cyan]Create New Instance[/bold cyan]\n\n[bold]Step 2: Select Version for '{name}'[/bold]\n\n"
            "  [1]  19.0          (Latest stable)\n"
            "  [2]  18.0          (Previous stable)\n"
            "  [3]  17.0          (Previous stable)\n"
            "  [4]  16.0          (Previous stable)\n"
            "  [5]  master        (Development)\n"
            "\n  [0]  Cancel",
            border_style="cyan"
        ))

        version_choice = input("\nSelect version (1-5): ").strip()
        versions = {"1": "19.0", "2": "18.0", "3": "17.0", "4": "16.0", "5": "master"}
        version = versions.get(version_choice)
        if not version:
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        # Step 3: Edition
        console.clear()
        console.print(Panel(
            f"[bold cyan]Create New Instance[/bold cyan]\n\n[bold]Step 3: Select Edition for '{name}'[/bold]\n\n"
            "  [1]  Community      (Free, open source)\n"
            "  [2]  Enterprise     (Paid, with extra features)\n"
            "\n  [0]  Cancel",
            border_style="cyan"
        ))

        edition_choice = input("\nSelect edition (1-2): ").strip()
        editions = {"1": "community", "2": "enterprise"}
        edition = editions.get(edition_choice)
        if not edition:
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        # Step 4: Port
        console.clear()
        console.print(Panel(
            f"[bold cyan]Create New Instance[/bold cyan]\n\n[bold]Step 4: Select Port for '{name}'[/bold]\n\n"
            "  [1]  8069          (Default)\n"
            "  [2]  8070\n"
            "  [3]  8071\n"
            "  [4]  8072\n"
            "  [5]  Custom port\n"
            "\n  [0]  Cancel",
            border_style="cyan"
        ))

        port_choice = input("\nSelect port (1-5): ").strip()
        ports = {"1": 8069, "2": 8070, "3": 8071, "4": 8072}
        if port_choice == "5":
            port = input("Enter custom port: ").strip()
            try:
                port = int(port)
            except:
                console.print("[red]Invalid port[/red]")
                input("\nPress Enter to continue...")
                return
        else:
            port = ports.get(port_choice, 8069)

        # Step 5: Workers
        console.clear()
        console.print(Panel(
            f"[bold cyan]Create New Instance[/bold cyan]\n\n[bold]Step 5: Select Workers for '{name}'[/bold]\n\n"
            "  [1]  2             (Small)\n"
            "  [2]  4             (Medium, recommended)\n"
            "  [3]  8             (Large)\n"
            "  [4]  16            (Very large)\n"
            "\n  [0]  Cancel",
            border_style="cyan"
        ))

        workers_choice = input("\nSelect workers (1-4): ").strip()
        workers = {"1": 2, "2": 4, "3": 8, "4": 16}
        workers_count = workers.get(workers_choice, 4)

        # Step 6: Deployment
        console.clear()
        console.print(Panel(
            f"[bold cyan]Create New Instance[/bold cyan]\n\n[bold]Step 6: Select Deployment for '{name}'[/bold]\n\n"
            "  [1]  Docker         (Recommended, isolated)\n"
            "  [2]  Source         (System-wide installation)\n"
            "\n  [0]  Cancel",
            border_style="cyan"
        ))

        deploy_choice = input("\nSelect deployment (1-2): ").strip()
        deployment = "docker" if deploy_choice == "1" else "source" if deploy_choice == "2" else None
        if deploy_choice == "0":
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        # Step 7: Confirm
        console.clear()
        console.print(Panel(
            f"[bold cyan]Create New Instance[/bold cyan]\n\n[bold]Step 7: Confirm[/bold]\n\n"
            f"  Name:       [cyan]{name}[/cyan]\n"
            f"  Version:    [cyan]{version}[/cyan]\n"
            f"  Edition:    [cyan]{edition.title()}[/cyan]\n"
            f"  Port:       [cyan]{port}[/cyan]\n"
            f"  Workers:    [cyan]{workers_count}[/cyan]\n"
            f"  Deployment: [cyan]{deployment.title()}[/cyan]\n"
            "\n  [1]  Create Instance"
            "\n  [0]  Cancel",
            border_style="cyan"
        ))

        confirm = input("\nConfirm? (1=Create, 0=Cancel): ").strip()
        if confirm != "1":
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        # Create the instance
        console.print("\n[dim]Creating instance...[/dim]")
        try:
            manager = InstanceManager()
            manager.create_instance(
                name=name,
                version=version,
                edition=edition,
                port=port,
                workers=workers_count,
                deployment_type=deployment,
            )
            console.print(f"[green]Instance '{name}' created successfully![/green]")
            console.print(f"\n[dim]Starting instance...[/dim]")
            instance = manager.get_instance(name)
            instance.start()
            console.print(f"[green]Instance '{name}' started![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    # ===== Database Operations =====
    def create_database(self, instance_name: str):
        """Create a new database."""
        console.print("\n[dim]Creating new database...[/dim]")
        db_name = input("Enter database name: ").strip()
        if not db_name:
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            db_manager = DatabaseManager(instance)
            db_manager.create(db_name)
            console.print(f"[green]Database '{db_name}' created![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    def drop_database(self, instance_name: str):
        """Drop a database."""
        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            db_manager = DatabaseManager(instance)
            databases = db_manager.list_databases()

            console.print("\nAvailable databases:")
            for i, db in enumerate(databases, 1):
                console.print(f"  [{i}]  {db}")

            choice = input("\nSelect database to drop: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(databases):
                db_name = databases[int(choice) - 1]
                if input(f"\nDrop database '{db_name}'? (yes/no): ").strip().lower() == "yes":
                    db_manager.drop(db_name)
                    console.print(f"[green]Database '{db_name}' dropped![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    def backup_database(self, instance_name: str):
        """Backup a database."""
        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            db_manager = DatabaseManager(instance)
            databases = db_manager.list_databases()

            console.print("\nAvailable databases:")
            for i, db in enumerate(databases, 1):
                console.print(f"  [{i}]  {db}")

            choice = input("\nSelect database to backup: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(databases):
                db_name = databases[int(choice) - 1]
                console.print(f"\n[dim]Backing up '{db_name}'...[/dim]")
                db_manager.backup(db_name)
                console.print(f"[green]Backup completed![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    def restore_database(self, instance_name: str):
        """Restore a database."""
        console.print("\n[dim]Available backups:[/dim]")
        # This would list available backups
        # For now, implement a simple version
        input("\nPress Enter to continue...")

    def duplicate_database(self, instance_name: str):
        """Duplicate a database."""
        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            db_manager = DatabaseManager(instance)
            databases = db_manager.list_databases()

            console.print("\nAvailable databases:")
            for i, db in enumerate(databases, 1):
                console.print(f"  [{i}]  {db}")

            choice = input("\nSelect database to duplicate: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(databases):
                source_db = databases[int(choice) - 1]
                new_name = input(f"\nEnter new database name (copy of {source_db}): ").strip()
                if new_name:
                    console.print(f"\n[dim]Duplicating '{source_db}' to '{new_name}'...[/dim]")
                    db_manager.duplicate(source_db, new_name)
                    console.print(f"[green]Database duplicated![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    # ===== Module Operations =====
    def install_modules(self, instance_name: str):
        """Install modules."""
        module_names = input("\nEnter module names (comma-separated): ").strip()
        if not module_names:
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        modules = [m.strip() for m in module_names.split(",")]
        console.print(f"\n[dim]Installing modules: {', '.join(modules)}[/dim]")

        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            mod_manager = ModuleManager(instance)
            mod_manager.install(modules)
            console.print("[green]Modules installed![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    def uninstall_modules(self, instance_name: str):
        """Uninstall modules."""
        module_names = input("\nEnter module names (comma-separated): ").strip()
        if not module_names:
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        modules = [m.strip() for m in module_names.split(",")]
        console.print(f"\n[dim]Uninstalling modules: {', '.join(modules)}[/dim]")

        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            mod_manager = ModuleManager(instance)
            mod_manager.uninstall(modules)
            console.print("[green]Modules uninstalled![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    def update_modules(self, instance_name: str):
        """Update modules."""
        module_names = input("\nEnter module names (comma-separated, or 'all'): ").strip()
        if not module_names:
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        console.print(f"\n[dim]Updating modules...[/dim]")

        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            mod_manager = ModuleManager(instance)

            if module_names.lower() == "all":
                mod_manager.update_all()
            else:
                modules = [m.strip() for m in module_names.split(",")]
                mod_manager.update(modules)

            console.print("[green]Modules updated![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    def upgrade_modules(self, instance_name: str):
        """Upgrade all modules."""
        console.print("\n[dim]Upgrading all modules...[/dim]")
        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            mod_manager = ModuleManager(instance)
            mod_manager.upgrade_all()
            console.print("[green]All modules upgraded![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    def search_module(self, instance_name: str):
        """Search for a module."""
        query = input("\nEnter search term: ").strip()
        if not query:
            console.print("[yellow]Cancelled[/yellow]")
            input("\nPress Enter to continue...")
            return

        console.print(f"\n[dim]Searching for '{query}'...[/dim]")
        # This would search through available modules
        # For now, show placeholder
        console.print("[yellow]Module search not yet implemented[/yellow]")
        input("\nPress Enter to continue...")

    # ===== Backup Operations =====
    def create_backup(self, instance_name: str):
        """Create a backup."""
        console.print("\n[bold]Backup Options[/bold]")
        console.print("  [1]  Full backup     (All databases)")
        console.print("  [2]  Database        (Single database)")
        console.print("  [3]  File system     (Files only)")

        choice = input("\nSelect backup type: ").strip()

        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            backup_manager = BackupManager(instance)

            console.print("\n[dim]Creating backup...[/dim]")

            if choice == "1":
                backup_manager.create_backup("full")
            elif choice == "2":
                db_name = input("Enter database name: ").strip()
                backup_manager.create_backup(db_name)
            elif choice == "3":
                backup_manager.create_backup("files")
            else:
                console.print("[yellow]Invalid choice[/yellow]")
                input("\nPress Enter to continue...")
                return

            console.print("[green]Backup completed![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    def restore_backup(self, instance_name: str):
        """Restore from backup."""
        console.print("\n[dim]Available backups:[/dim]")
        # List backups would go here
        input("\nPress Enter to continue...")

    def schedule_backup(self, instance_name: str):
        """Configure backup schedule."""
        console.print("\n[bold]Backup Schedule[/bold]")
        console.print("  [1]  Daily          Every day at 2 AM")
        console.print("  [2]  Weekly         Every Sunday at 2 AM")
        console.print("  [3]  Custom         Custom schedule")
        console.print("\n  [0]  Cancel")

        choice = input("\nSelect schedule: ").strip()

        if choice == "0":
            return

        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            backup_manager = BackupManager(instance)

            if choice == "1":
                backup_manager.schedule_backup("daily", "02:00")
                console.print("[green]Daily backup scheduled![/green]")
            elif choice == "2":
                backup_manager.schedule_backup("weekly", "sunday", "02:00")
                console.print("[green]Weekly backup scheduled![/green]")
            elif choice == "3":
                console.print("[yellow]Custom scheduling not yet implemented[/yellow]")

            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            input("\nPress Enter to continue...")

    def delete_backup(self, instance_name: str):
        """Delete a backup."""
        console.print("\n[dim]Backup deletion not yet implemented[/dim]")
        input("\nPress Enter to continue...")

    # ===== Log Viewing =====
    def view_logs(self, instance_name: str):
        """View logs for an instance."""
        console.clear()
        console.print(Panel(f"[bold cyan]Logs: {instance_name}[/bold cyan]", border_style="cyan"))

        console.print("\n[bold]Options[/bold]")
        console.print("  [1]  Show last 100 lines")
        console.print("  [2]  Show last 500 lines")
        console.print("  [3]  Follow mode (live)")
        console.print("  [4]  Filter by keyword")
        console.print("\n  [0]  Back")

        choice = input("\nSelect option: ").strip()

        if choice == "0":
            return
        elif choice == "1":
            self._show_logs_content(instance_name, 100)
        elif choice == "2":
            self._show_logs_content(instance_name, 500)
        elif choice == "3":
            self._follow_logs(instance_name)
        elif choice == "4":
            keyword = input("\nEnter keyword: ").strip()
            self._show_logs_content(instance_name, 100, keyword)

    def _show_logs_content(self, instance_name: str, lines: int, keyword: str = None):
        """Show log content."""
        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            logs = instance.get_logs(tail=lines, follow=False)

            if keyword:
                logs = [line for line in logs.split('\n') if keyword.lower() in line.lower()]

            console.print(f"\n[dim]Showing last {lines} lines[/dim]\n")
            console.print(logs[:2000])  # Limit output

        except Exception as e:
            console.print(f"[red]Failed to get logs: {e}[/red]")

        input("\nPress Enter to continue...")

    def _follow_logs(self, instance_name: str):
        """Follow logs in real-time."""
        console.print("\n[dim]Following logs... (Press Ctrl+C to stop)[/dim]\n")
        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)

            # Stream logs
            for line in instance.get_logs(follow=True):
                console.print(line, end="")
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Log following stopped[/yellow]")
            input("\nPress Enter to continue...")

    # ===== Shell Access =====
    def open_shell(self, instance_name: str):
        """Open Odoo Python shell."""
        console.print(f"\n[dim]Opening shell for '{instance_name}'...[/dim]\n")
        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            instance.exec_command(["python", "-c",
                "import odoo; odoo.cli.Shell().run(['-c', 'config', '-d', odoo.tools.config['db_name']])"
            ])
        except Exception as e:
            console.print(f"[red]Failed to open shell: {e}[/red]")

        input("\nPress Enter to continue...")

    # ===== Instance Actions =====
    def do_instance_action(self, name: str, action: str):
        """Perform an action on an instance."""
        console.print(f"\n[dim]Performing: {action} on '{name}'...[/dim]")
        try:
            manager = InstanceManager()
            instance = manager.get_instance(name)

            if action == "start":
                instance.start()
                console.print(f"[green]Started '{name}'[/green]")
            elif action == "stop":
                instance.stop()
                console.print(f"[yellow]Stopped '{name}'[/yellow]")
            elif action == "restart":
                instance.restart()
                console.print(f"[yellow]Restarted '{name}'[/yellow]")
            elif action == "remove":
                instance.remove()
                manager.remove_instance(name)
                console.print(f"[red]Removed '{name}'[/red]")

            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Action failed: {e}[/red]")
            input("\nPress Enter to continue...")

    # ===== Helper Methods =====
    def get_instances_list(self, running_only: bool = False):
        """Get list of instances."""
        try:
            manager = InstanceManager()
            instances = manager.list_instances()
            monitor = HealthMonitor()

            instance_list = []
            for inst in instances:
                is_running = inst.is_running()
                if running_only and not is_running:
                    continue
                health = monitor.check_instance(inst)
                instance_list.append({
                    "name": inst.config.name,
                    "version": inst.config.version,
                    "status": inst.status(),
                    "running": is_running,
                    "port": inst.config.port,
                })
            return instance_list
        except:
            return []

    def show_placeholder(self, title: str):
        """Show a placeholder for unimplemented features."""
        console.clear()
        console.print(Panel(
            f"[bold cyan]{title}[/bold cyan]\n\n[yellow]This feature is coming soon![/yellow]",
            border_style="cyan"
        ))
        input("\nPress Enter to continue...")


def launch_tui():
    """Launch the simple TUI."""
    app = SimpleTUI()
    app.run()
