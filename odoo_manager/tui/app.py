"""
Terminal User Interface (TUI) for Odoo Manager using Textual.

A simple menu-driven interface where you select options by number.
"""

from enum import Enum
from typing import Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header,
    Footer,
    Static,
    DataTable,
    Button,
    Input,
    Label,
)
from textual.binding import Binding
from textual.screen import ModalScreen
from textual import on

from odoo_manager.core.instance import InstanceManager
from odoo_manager.core.monitor import HealthMonitor


class AppState(str, Enum):
    """Application states."""
    MENU = "menu"
    INSTANCES = "instances"
    CREATE_INSTANCE = "create_instance"
    INSTANCE_ACTIONS = "instance_actions"


class MainMenu(Container):
    """Main menu with numbered options."""

    def compose(self) -> ComposeResult:
        """Compose the main menu."""
        yield Static(
            """[bold cyan]Odoo Manager[/bold cyan] [dim]v0.1.0[/dim]

A local Odoo instance management tool

[bold]Main Menu[/bold]""",
            id="menu_header"
        )
        yield Static(
            """  [1] [cyan]Instances[/cyan]       Manage Odoo instances
  [2] [cyan]Databases[/cyan]       Manage databases
  [3] [cyan]Modules[/cyan]         Install/Update modules
  [4] [cyan]Backups[/cyan]         Backup & Restore
  [5] [cyan]Logs[/cyan]            View logs
  [6] [cyan]Config[/cyan]          Configuration
  [Q] [dim]Quit[/dim]""",
            id="menu_options"
        )
        yield Static("Enter option (1-6, Q):", id="menu_prompt")


class InstanceList(Container):
    """Instance list with numbered options."""

    instances: list = []

    def on_mount(self) -> None:
        """Load instances when mounted."""
        self.refresh_instances()

    def refresh_instances(self) -> None:
        """Refresh the instance list."""
        try:
            manager = InstanceManager()
            instances = manager.list_instances()
            monitor = HealthMonitor()

            self.instances = []
            for inst in instances:
                health = monitor.check_instance(inst)
                self.instances.append({
                    "name": inst.config.name,
                    "version": inst.config.version,
                    "status": inst.status(),
                    "running": inst.is_running(),
                    "port": inst.config.port,
                })
        except Exception:
            self.instances = []

        self.update_display()

    def update_display(self) -> None:
        """Update the display."""
        content = Static(id="instance_list")
        self.remove_children()
        self.mount(content)

        if not self.instances:
            content.update("[yellow]No instances found.[/yellow]\n\n[0] Return to menu")
            return

        text = "[bold]Odoo Instances[/bold]\n\n"
        for i, inst in enumerate(self.instances, 1):
            status = "[green]RUNNING[/green]" if inst["running"] else "[red]STOPPED[/red]"
            text += f"  [{i}] {inst['name']:20} {status:15} v{inst['version']} :{inst['port']}\n"

        text += "\n[0] Return to menu"
        content.update(Text.from_markup(text))

    def compose(self) -> ComposeResult:
        """Compose the instance list."""
        yield Static(id="instance_list")


class CreateInstanceForm(Container):
    """Form to create a new instance."""

    def compose(self) -> ComposeResult:
        """Compose the form."""
        yield Static(
            """[bold cyan]Create New Instance[/bold cyan]

Step 1: Enter Instance Name
━━━━━━━━━━━━━━━━━━━━━━━━━━


[0] Cancel""",
            id="create_header"
        )
        yield Input(placeholder="Enter instance name...", id="input_name")


class CreateInstanceStep2(Container):
    """Step 2: Select version."""

    instance_name: str = ""

    def __init__(self, name: str, **kwargs):
        super().__init__(**kwargs)
        self.instance_name = name

    def compose(self) -> ComposeResult:
        """Compose the form."""
        yield Static(
            f"""[bold cyan]Create New Instance[/bold cyan]

Step 2: Select Version for '[cyan]{self.instance_name}[/cyan]'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


  [1] [cyan]19.0[/cyan]           (Latest stable)
  [2] [cyan]18.0[/cyan]           (Previous stable)
  [3] [cyan]17.0[/cyan]           (Previous stable)
  [4] [cyan]master[/cyan]         (Development)

[0] Cancel"""
        )


class CreateInstanceStep3(Container):
    """Step 3: Select edition."""

    instance_name: str = ""
    version: str = ""

    def __init__(self, name: str, version: str, **kwargs):
        super().__init__(**kwargs)
        self.instance_name = name
        self.version = version

    def compose(self) -> ComposeResult:
        """Compose the form."""
        yield Static(
            f"""[bold cyan]Create New Instance[/bold cyan]

Step 3: Select Edition for '[cyan]{self.instance_name}[/cyan]'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


  [1] [cyan]Community[/cyan]     (Free, open source)
  [2] [cyan]Enterprise[/cyan]    (Paid, with extra features)

[0] Cancel"""
        )


class CreateInstanceConfirm(Container):
    """Confirm and create instance."""

    instance_name: str = ""
    version: str = ""
    edition: str = ""

    def __init__(self, name: str, version: str, edition: str, **kwargs):
        super().__init__(**kwargs)
        self.instance_name = name
        self.version = version
        self.edition = edition

    def compose(self) -> ComposeResult:
        """Compose the confirmation."""
        yield Static(
            f"""[bold cyan]Create New Instance[/bold cyan]

Step 4: Confirm
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Name:     [cyan]{self.instance_name}[/cyan]
  Version:  [cyan]{self.version}[/cyan]
  Edition:  [cyan]{self.edition}[/cyan]
  Port:     [cyan]8069[/cyan] (default)
  Workers:  [cyan]4[/cyan] (default)


  [1] [green]Create Instance[/green]
  [0] Cancel"""
        )


class InstanceActions(Container):
    """Actions for a specific instance."""

    instance_name: str = ""
    instance_info: dict = {}

    def __init__(self, instance_info: dict, **kwargs):
        super().__init__(**kwargs)
        self.instance_name = instance_info["name"]
        self.instance_info = instance_info

    def compose(self) -> ComposeResult:
        """Compose the actions."""
        status_color = "green" if self.instance_info["running"] else "red"
        yield Static(
            f"""[bold cyan]Instance: {self.instance_name}[/bold cyan]

  Status:   [{status_color}]{self.instance_info['status'].upper()}[/{status_color}]
  Version:  {self.instance_info['version']}
  Port:     :{self.instance_info['port']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  [1] [green]Start[/green]         Start the instance
  [2] [red]Stop[/red]            Stop the instance
  [3] [yellow]Restart[/yellow]       Restart the instance
  [4] [cyan]Logs[/cyan]            View logs
  [5] [red]Remove[/red]           Delete instance

[0] Back to instances"""
        )


class OdooManagerTUI(App):
    """Main TUI application - simple numbered menu."""

    CSS = """
    Screen {
        background: $background;
    }

    #main_container {
        padding: 2 4;
    }

    Static {
        margin: 1 0;
    }

    Input {
        margin: 1 0;
        width: 40;
    }
    """

    TITLE = "Odoo Manager"
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("0", "back", "Back", show=True),
    ]

    # State
    current_state: AppState = AppState.MENU
    create_data: dict = {}

    def compose(self) -> ComposeResult:
        """Compose the application."""
        yield Header()
        yield Container(id="main_container")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize on mount."""
        self.show_main_menu()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if self.current_state == AppState.CREATE_INSTANCE:
            name = event.value.strip()
            if name:
                self.create_data["name"] = name
                self.show_create_step2(name)
            else:
                self.show_main_menu()

    def on_key(self, event) -> None:
        """Handle key presses for menu navigation."""
        if event.key == "q" or event.key == "Q":
            self.exit()
        elif event.character and event.character.isdigit():
            self.handle_menu_input(int(event.character))

    def handle_menu_input(self, choice: int) -> None:
        """Handle menu number input."""
        if self.current_state == AppState.MENU:
            if choice == 1:
                self.show_instances()
            elif choice == 2:
                self.show_message("Databases", "Coming soon...")
            elif choice == 3:
                self.show_message("Modules", "Coming soon...")
            elif choice == 4:
                self.show_message("Backups", "Coming soon...")
            elif choice == 5:
                self.show_message("Logs", "Coming soon...")
            elif choice == 6:
                self.show_message("Config", "Coming soon...")

        elif self.current_state == AppState.INSTANCES:
            if choice == 0:
                self.show_main_menu()
            elif 1 <= choice <= len(self.query_one(InstanceList).instances):
                inst = self.query_one(InstanceList).instances[choice - 1]
                self.show_instance_actions(inst)

        elif self.current_state == AppState.INSTANCE_ACTIONS:
            if choice == 0:
                self.show_instances()
            elif choice == 1:  # Start
                self._instance_action("start")
            elif choice == 2:  # Stop
                self._instance_action("stop")
            elif choice == 3:  # Restart
                self._instance_action("restart")
            elif choice == 4:  # Logs
                self.show_message("Logs", f"Logs for {self.create_data.get('instance_name', 'N/A')}...\n\nComing soon...")
                self.show_instances()
            elif choice == 5:  # Remove
                self._instance_action("remove")

        elif self.current_state == AppState.CREATE_INSTANCE:
            if choice == 0:
                self.show_instances()

    def show_main_menu(self) -> None:
        """Show main menu."""
        self.current_state = AppState.MENU
        self.create_data = {}
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(MainMenu())

    def show_instances(self) -> None:
        """Show instances list."""
        self.current_state = AppState.INSTANCES
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(InstanceList())

    def show_create_step1(self) -> None:
        """Show create instance step 1 - enter name."""
        self.current_state = AppState.CREATE_INSTANCE
        self.create_data = {}
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(CreateInstanceForm())
        # Focus on input
        input_widget = self.query_one(Input)
        input_widget.focus()

    def show_create_step2(self, name: str) -> None:
        """Show create instance step 2 - select version."""
        self.create_data["name"] = name
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(CreateInstanceStep2(name))

    def show_create_step3(self, name: str, version: str) -> None:
        """Show create instance step 3 - select edition."""
        self.create_data["name"] = name
        self.create_data["version"] = version
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(CreateInstanceStep3(name, version))

    def show_create_confirm(self, name: str, version: str, edition: str) -> None:
        """Show create instance confirmation."""
        self.create_data["name"] = name
        self.create_data["version"] = version
        self.create_data["edition"] = edition
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(CreateInstanceConfirm(name, version, edition))

    def show_instance_actions(self, instance: dict) -> None:
        """Show actions for an instance."""
        self.current_state = AppState.INSTANCE_ACTIONS
        self.create_data["instance_name"] = instance["name"]
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(InstanceActions(instance))

    def show_message(self, title: str, message: str) -> None:
        """Show a simple message."""
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(
            Static(
                f"[bold cyan]{title}[/bold cyan]\n\n{message}\n\n[0] OK"
            )
        )

    def _instance_action(self, action: str) -> None:
        """Perform an instance action."""
        name = self.create_data.get("instance_name")
        try:
            manager = InstanceManager()
            instance = manager.get_instance(name)

            if action == "start":
                instance.start()
                self.notify(f"Started '{name}'")
            elif action == "stop":
                instance.stop()
                self.notify(f"Stopped '{name}'")
            elif action == "restart":
                instance.restart()
                self.notify(f"Restarted '{name}'")
            elif action == "remove":
                instance.remove()
                manager.remove_instance(name)
                self.notify(f"Removed '{name}'")

            self.show_instances()

        except Exception as e:
            self.show_message("Error", f"Action failed: {e}")
            if action != "remove":
                self.show_instances()

    # Handlers for create instance screens
    def on_key_create_step2(self, choice: int) -> None:
        """Handle step 2 input."""
        name = self.create_data.get("name", "")
        versions = ["19.0", "18.0", "17.0", "master"]
        if choice == 0:
            self.show_instances()
        elif 1 <= choice <= len(versions):
            self.show_create_step3(name, versions[choice - 1])

    def on_key_create_step3(self, choice: int) -> None:
        """Handle step 3 input."""
        name = self.create_data.get("name", "")
        version = self.create_data.get("version", "")
        editions = ["community", "enterprise"]
        if choice == 0:
            self.show_instances()
        elif choice == 1:
            self.show_create_confirm(name, version, "Community")
        elif choice == 2:
            self.show_create_confirm(name, version, "Enterprise")

    def on_key_create_confirm(self, choice: int) -> None:
        """Handle confirm input."""
        if choice == 0:
            self.show_instances()
        elif choice == 1:
            self._do_create_instance()

    def _do_create_instance(self) -> None:
        """Actually create the instance."""
        try:
            manager = InstanceManager()
            manager.create_instance(
                name=self.create_data["name"],
                version=self.create_data["version"],
                edition=self.create_data["edition"].lower(),
                port=8069,
                workers=4,
                deployment_type="docker",
            )
            self.show_message("Success", f"Instance '{self.create_data['name']}' created successfully!")
            self.show_instances()
        except Exception as e:
            self.show_message("Error", f"Failed to create instance: {e}")

    # Override on_key to route to specific handlers
    def on_key(self, event) -> None:
        """Handle key presses with routing to current state handler."""
        if event.key == "q" or event.key == "Q":
            self.exit()
            return

        if not event.character or not event.character.isdigit():
            return

        choice = int(event.character)

        if choice == 0:
            if self.current_state in [AppState.CREATE_INSTANCE, AppState.INSTANCE_ACTIONS]:
                self.show_instances()
            else:
                self.show_main_menu()
            return

        if self.current_state == AppState.MENU:
            self.handle_menu_input(choice)
        elif self.current_state == AppState.INSTANCES:
            self.handle_menu_input(choice)
        elif self.current_state == AppState.INSTANCE_ACTIONS:
            self.handle_menu_input(choice)
        elif self.current_state == AppState.CREATE_INSTANCE:
            # Check which step we're on
            main = self.query_one("#main_container", Container)
            if isinstance(main.children[0], CreateInstanceStep2):
                self.on_key_create_step2(choice)
            elif isinstance(main.children[0], CreateInstanceStep3):
                self.on_key_create_step3(choice)
            elif isinstance(main.children[0], CreateInstanceConfirm):
                self.on_key_create_confirm(choice)


def launch_tui():
    """Launch the TUI application."""
    app = OdooManagerTUI()
    app.run()
