"""
Terminal User Interface (TUI) for Odoo Manager using Textual.

A simple menu-driven interface where you select options by number.
"""

from enum import Enum
from typing import Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import (
    Header,
    Footer,
    Static,
    Input,
)
from textual.binding import Binding
from textual import on

from odoo_manager.core.instance import InstanceManager
from odoo_manager.core.monitor import HealthMonitor


class AppState(str, Enum):
    """Application states."""
    MENU = "menu"
    INSTANCES = "instances"
    CREATE_STEP_NAME = "create_name"
    CREATE_STEP_VERSION = "create_version"
    CREATE_STEP_EDITION = "create_edition"
    CREATE_STEP_CONFIRM = "create_confirm"
    INSTANCE_ACTIONS = "instance_actions"


class MainMenu(Container):
    """Main menu with numbered options."""

    def compose(self) -> ComposeResult:
        """Compose the main menu."""
        yield Static(
            """[bold cyan]Odoo Manager[/bold cyan] [dim]v0.1.0[/dim]

A local Odoo instance management tool

[bold]Main Menu[/bold]

  [1] [cyan]Instances[/cyan]       Manage Odoo instances
  [2] [cyan]Databases[/cyan]       Manage databases
  [3] [cyan]Modules[/cyan]         Install/Update modules
  [4] [cyan]Backups[/cyan]         Backup & Restore
  [5] [cyan]Logs[/cyan]            View logs
  [6] [cyan]Config[/cyan]          Configuration

  [Q] [dim]Quit[/dim]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press a number (1-6) or Q to quit"""
        )


class InstanceList(Container):
    """Instance list with numbered options."""

    instances: list = []
    content: Static = None

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
        if self.content is None:
            self.content = Static()
            self.mount(self.content)

        if not self.instances:
            self.content.update(
                """[bold cyan]Odoo Instances[/bold cyan]

[yellow]No instances found.[/yellow]

  [1] [green]Create New Instance[/green]
  [0] Back to main menu

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press a number to select"""
            )
            return

        text = "[bold cyan]Odoo Instances[/bold cyan]\n\n"
        for i, inst in enumerate(self.instances, 1):
            status = "[green]RUNNING[/green]" if inst["running"] else "[red]STOPPED[/red]"
            text += f"  [{i}] {inst['name']:20} {status:15} v{inst['version']:6} :{inst['port']}\n"

        text += "\n  [C] [green]Create New Instance[/green]"
        text += "\n  [0] Back to main menu"

        text += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        text += "\n\nPress a number (1-{}) or 0 to go back".format(len(self.instances))

        self.content.update(Text.from_markup(text))


class CreateNameStep(Container):
    """Step 1: Enter instance name."""

    content: Static = None
    name_input: Input = None

    def compose(self) -> ComposeResult:
        """Compose the form."""
        self.content = Static(
            """[bold cyan]Create New Instance[/bold cyan]

Step 1: Enter Instance Name
━━━━━━━━━━━━━━━━━━━━━━━━━━

  [0] Cancel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        )
        yield self.content
        self.name_input = Input(placeholder="Enter instance name...")
        yield self.name_input

    def on_mount(self) -> None:
        """Focus input on mount."""
        self.name_input.focus()


class CreateVersionStep(Container):
    """Step 2: Select version."""

    content: Static = None

    def __init__(self, name: str, **kwargs):
        super().__init__(**kwargs)
        self.instance_name = name

    def compose(self) -> ComposeResult:
        """Compose the form."""
        self.content = Static(
            f"""[bold cyan]Create New Instance[/bold cyan]

Step 2: Select Version for '[cyan]{self.instance_name}[/cyan]'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  [1] [cyan]19.0[/cyan]           (Latest stable)
  [2] [cyan]18.0[/cyan]           (Previous stable)
  [3] [cyan]17.0[/cyan]           (Previous stable)
  [4] [cyan]master[/cyan]         (Development)

  [0] Cancel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press a number (1-4) to select version"""
        )
        yield self.content


class CreateEditionStep(Container):
    """Step 3: Select edition."""

    content: Static = None

    def __init__(self, name: str, version: str, **kwargs):
        super().__init__(**kwargs)
        self.instance_name = name
        self.version = version

    def compose(self) -> ComposeResult:
        """Compose the form."""
        self.content = Static(
            f"""[bold cyan]Create New Instance[/bold cyan]

Step 3: Select Edition for '[cyan]{self.instance_name}[/cyan]'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  [1] [cyan]Community[/cyan]     (Free, open source)
  [2] [cyan]Enterprise[/cyan]    (Paid, with extra features)

  [0] Cancel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press a number (1-2) to select edition"""
        )
        yield self.content


class CreateConfirmStep(Container):
    """Step 4: Confirm and create."""

    content: Static = None

    def __init__(self, name: str, version: str, edition: str, **kwargs):
        super().__init__(**kwargs)
        self.instance_name = name
        self.version = version
        self.edition = edition

    def compose(self) -> ComposeResult:
        """Compose the confirmation."""
        self.content = Static(
            f"""[bold cyan]Create New Instance[/bold cyan]

Step 4: Confirm
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Name:     [cyan]{self.instance_name}[/cyan]
  Version:  [cyan]{self.version}[/cyan]
  Edition:  [cyan]{self.edition}[/cyan]
  Port:     [cyan]8069[/cyan] (default)
  Workers:  [cyan]4[/cyan] (default)

  [1] [green]Create Instance[/green]
  [0] Cancel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press 1 to create or 0 to cancel"""
        )
        yield self.content


class InstanceActions(Container):
    """Actions for a specific instance."""

    content: Static = None

    def __init__(self, instance_info: dict, **kwargs):
        super().__init__(**kwargs)
        self.instance_name = instance_info["name"]
        self.instance_info = instance_info

    def compose(self) -> ComposeResult:
        """Compose the actions."""
        status_color = "green" if self.instance_info["running"] else "red"
        self.content = Static(
            f"""[bold cyan]Instance: {self.instance_name}[/bold cyan]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Status:   [{status_color}]{self.instance_info['status'].upper()}[/{status_color}]
  Version:  {self.instance_info['version']}
  Port:     :{self.instance_info['port']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  [1] [green]Start[/green]         Start the instance
  [2] [red]Stop[/red]            Stop the instance
  [3] [yellow]Restart[/yellow]       Restart the instance
  [4] [cyan]Logs[/cyan]            View logs
  [5] [red]Remove[/red]           Delete instance

  [0] Back to instances

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press a number (1-5) or 0 to go back"""
        )
        yield self.content


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

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (for instance name)."""
        if self.current_state == AppState.CREATE_STEP_NAME:
            name = event.value.strip()
            if name:
                self.create_data["name"] = name
                self.show_create_version(name)
            else:
                self.show_instances()

    def on_key(self, event) -> None:
        """Handle key presses for menu navigation."""
        # Quit
        if event.key == "q" or event.key == "Q":
            self.exit()
            return

        # Handle digit input
        if event.character and event.character.isdigit():
            self.handle_number_input(int(event.character))
            return

        # Handle 'c' for create from instances screen
        if event.key == "c" or event.key == "C":
            if self.current_state == AppState.INSTANCES:
                self.show_create_name()
            return

        # Handle '0' for back
        if event.key == "0":
            self.handle_back()

    def handle_number_input(self, choice: int) -> None:
        """Handle number key input."""
        if self.current_state == AppState.MENU:
            if choice == 1:
                self.show_instances()
            elif choice == 2:
                self.show_placeholder("Databases")
            elif choice == 3:
                self.show_placeholder("Modules")
            elif choice == 4:
                self.show_placeholder("Backups")
            elif choice == 5:
                self.show_placeholder("Logs")
            elif choice == 6:
                self.show_placeholder("Config")

        elif self.current_state == AppState.INSTANCES:
            if 1 <= choice <= len(self.get_instance_list().instances):
                inst = self.get_instance_list().instances[choice - 1]
                self.show_instance_actions(inst)

        elif self.current_state == AppState.CREATE_STEP_VERSION:
            versions = ["19.0", "18.0", "17.0", "master"]
            if 1 <= choice <= len(versions):
                self.show_create_edition(self.create_data["name"], versions[choice - 1])

        elif self.current_state == AppState.CREATE_STEP_EDITION:
            if choice == 1:
                self.show_create_confirm(
                    self.create_data["name"],
                    self.create_data["version"],
                    "Community"
                )
            elif choice == 2:
                self.show_create_confirm(
                    self.create_data["name"],
                    self.create_data["version"],
                    "Enterprise"
                )

        elif self.current_state == AppState.CREATE_STEP_CONFIRM:
            if choice == 1:
                self.do_create_instance()

        elif self.current_state == AppState.INSTANCE_ACTIONS:
            if choice == 1:
                self.instance_action("start")
            elif choice == 2:
                self.instance_action("stop")
            elif choice == 3:
                self.instance_action("restart")
            elif choice == 4:
                self.show_placeholder("Logs")
                self.show_instances()
            elif choice == 5:
                self.instance_action("remove")

        elif self.current_state == AppState.PLACEHOLDER:
            self.show_instances()

    def handle_back(self) -> None:
        """Handle back navigation."""
        if self.current_state == AppState.INSTANCES:
            self.show_main_menu()
        elif self.current_state in [
            AppState.CREATE_STEP_NAME,
            AppState.CREATE_STEP_VERSION,
            AppState.CREATE_STEP_EDITION,
            AppState.CREATE_STEP_CONFIRM,
            AppState.INSTANCE_ACTIONS,
        ]:
            self.show_instances()
        else:
            self.show_main_menu()

    def get_instance_list(self) -> InstanceList:
        """Get the current instance list widget."""
        main = self.query_one("#main_container", Container)
        if main.children and isinstance(main.children[0], InstanceList):
            return main.children[0]
        return None

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

    def show_create_name(self) -> None:
        """Show create instance step 1 - enter name."""
        self.current_state = AppState.CREATE_STEP_NAME
        self.create_data = {}
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(CreateNameStep())

    def show_create_version(self, name: str) -> None:
        """Show create instance step 2 - select version."""
        self.current_state = AppState.CREATE_STEP_VERSION
        self.create_data["name"] = name
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(CreateVersionStep(name))

    def show_create_edition(self, name: str, version: str) -> None:
        """Show create instance step 3 - select edition."""
        self.current_state = AppState.CREATE_STEP_EDITION
        self.create_data["name"] = name
        self.create_data["version"] = version
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(CreateEditionStep(name, version))

    def show_create_confirm(self, name: str, version: str, edition: str) -> None:
        """Show create instance confirmation."""
        self.current_state = AppState.CREATE_STEP_CONFIRM
        self.create_data["name"] = name
        self.create_data["version"] = version
        self.create_data["edition"] = edition
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(CreateConfirmStep(name, version, edition))

    def show_instance_actions(self, instance: dict) -> None:
        """Show actions for an instance."""
        self.current_state = AppState.INSTANCE_ACTIONS
        self.create_data["instance_name"] = instance["name"]
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(InstanceActions(instance))

    def show_placeholder(self, title: str) -> None:
        """Show a placeholder for unimplemented features."""
        self.current_state = AppState.PLACEHOLDER
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(
            Static(
                f"""[bold cyan]{title}[/bold cyan]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[yellow]Coming soon...[/yellow]

  [0] Back to main menu

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press 0 to go back"""
            )
        )

    def do_create_instance(self) -> None:
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
            self.show_message(
                "Success",
                f"Instance '[cyan]{self.create_data['name']}[/cyan]' created successfully!",
                go_to_instances=True
            )
        except Exception as e:
            self.show_message("Error", f"[red]Failed to create instance:[/red]\n\n{e}")

    def instance_action(self, action: str) -> None:
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
            self.show_message("Error", f"[red]Action failed:[/red]\n\n{e}")

    def show_message(self, title: str, message: str, go_to_instances: bool = False) -> None:
        """Show a simple message."""
        main = self.query_one("#main_container", Container)
        main.remove_children()
        main.mount(
            Static(
                f"""[bold cyan]{title}[/bold cyan]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{message}

  [0] OK

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press 0 to continue"""
            )
        )
        if go_to_instances:
            # Auto-advance to instances after user presses 0
            self._go_to_instances_after_message = True

    def on_key(self, event) -> None:
        """Override to handle special case."""
        # Check for auto-advance after message
        if hasattr(self, '_go_to_instances_after_message') and event.key == '0':
            delattr(self, '_go_to_instances_after_message')
            self.show_instances()
            return

        # Original handler
        if event.key == "q" or event.key == "Q":
            self.exit()
            return

        if event.character and event.character.isdigit():
            self.handle_number_input(int(event.character))
            return

        if event.key == "c" or event.key == "C":
            if self.current_state == AppState.INSTANCES:
                self.show_create_name()
            return

        if event.key == "0":
            self.handle_back()


# Add PLACEHOLDER to AppState
AppState.PLACEHOLDER = "placeholder"


def launch_tui():
    """Launch the TUI application."""
    app = OdooManagerTUI()
    app.run()
