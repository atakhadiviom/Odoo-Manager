"""
Terminal UI for Odoo Manager - Simple numbered menu like a bash script.

No complex framework - just simple input/output.
"""

import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from odoo_manager.core.instance import InstanceManager
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

A local Odoo instance management tool

[bold]Main Menu[/bold]

  [1]  Instances       Manage Odoo instances
  [2]  Databases       Manage databases
  [3]  Modules         Install/Update modules
  [4]  Backups         Backup & Restore
  [5]  Logs            View logs
  [6]  Config          Configuration

  [0]  [dim]Quit[/dim]""",
                    title="📦 Odoo Manager",
                    border_style="cyan"
                )
            )

            choice = input("\nSelect option (0-6): ").strip()

            if choice == "0" or choice.lower() == "q":
                console.print("[yellow]Goodbye![/yellow]")
                self.running = False
                return
            elif choice == "1":
                self.show_instances()
            elif choice == "2":
                self.show_placeholder("Databases")
            elif choice == "3":
                self.show_placeholder("Modules")
            elif choice == "4":
                self.show_placeholder("Backups")
            elif choice == "5":
                self.show_placeholder("Logs")
            elif choice == "6":
                self.show_placeholder("Config")

    def show_instances(self):
        """Show instances menu."""
        while True:
            # Get instances
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
                    })
            except:
                instance_list = []

            console.clear()

            # Build menu
            menu_text = "[bold cyan]Odoo Instances[/bold cyan]\n\n"

            if not instance_list:
                menu_text += "[yellow]No instances found.[/yellow]\n"
            else:
                for i, inst in enumerate(instance_list, 1):
                    status = "[green]RUNNING[/green]" if inst["running"] else "[red]STOPPED[/red]"
                    menu_text += f"  [{i}]  {inst['name']:20} {status:15} v{inst['version']} :{inst['port']}\n"

            menu_text += "\n  [C]  Create New Instance"
            menu_text += "\n  [0]  Back to main menu"

            console.print(Panel(menu_text, border_style="cyan"))

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
            menu_text = f"[bold cyan]Instance: {instance['name']}[/bold cyan]\n\n"
            menu_text += f"  Status:   [{status_color}]{instance['status'].upper()}[/{status_color}]\n"
            menu_text += f"  Version:  {instance['version']}\n"
            menu_text += f"  Port:     :{instance['port']}\n"
            menu_text += "\n[bold]Actions[/bold]\n"
            menu_text += "  [1]  Start          Start the instance\n"
            menu_text += "  [2]  Stop           Stop the instance\n"
            menu_text += "  [3]  Restart        Restart the instance\n"
            menu_text += "  [4]  Logs           View logs\n"
            menu_text += "  [5]  Remove         Delete instance\n"
            menu_text += "\n  [0]  Back"

            console.print(Panel(menu_text, border_style="cyan"))

            choice = input(f"\nSelect action for {instance['name']}: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                self.do_instance_action(instance["name"], "start")
                if instance.get("running"):
                    # Status changed, refresh
                    return
            elif choice == "2":
                self.do_instance_action(instance["name"], "stop")
                if not instance.get("running"):
                    return
            elif choice == "3":
                self.do_instance_action(instance["name"], "restart")
            elif choice == "4":
                self.show_placeholder(f"Logs for {instance['name']}")
            elif choice == "5":
                if input(f"Remove '{instance['name']}'? (yes/no): ").strip().lower() == "yes":
                    self.do_instance_action(instance["name"], "remove")
                    return

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
            "  [4]  master        (Development)\n"
            "\n  [0]  Cancel",
            border_style="cyan"
        ))

        version_choice = input("\nSelect version (1-4): ").strip()
        versions = {"1": "19.0", "2": "18.0", "3": "17.0", "4": "master"}
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

        # Step 4: Confirm
        console.clear()
        console.print(Panel(
            f"[bold cyan]Create New Instance[/bold cyan]\n\n[bold]Step 4: Confirm[/bold]\n\n"
            f"  Name:     [cyan]{name}[/cyan]\n"
            f"  Version:  [cyan]{version}[/cyan]\n"
            f"  Edition:  [cyan]{edition.title()}[/cyan]\n"
            f"  Port:     [cyan]8069[/cyan] (default)\n"
            f"  Workers:  [cyan]4[/cyan] (default)\n"
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
                port=8069,
                workers=4,
                deployment_type="docker",
            )
            console.print(f"[green]Instance '{name}' created successfully![/green]")
            input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[red]Failed to create instance: {e}[/red]")
            input("\nPress Enter to continue...")

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

    def show_placeholder(self, title: str):
        """Show a placeholder for unimplemented features."""
        console.clear()
        console.print(Panel(
            f"[bold cyan]{title}[/bold cyan]\n\n[yellow]Coming soon...[/yellow]",
            border_style="cyan"
        ))
        input("\nPress Enter to continue...")


def launch_tui():
    """Launch the simple TUI."""
    app = SimpleTUI()
    app.run()
