"""
Terminal User Interface (TUI) for Odoo Manager using Textual.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from rich.console import RenderableType
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
    ProgressBar,
    ListItem,
    ListView,
    Placeholder,
    Log,
    Switch,
)
from textual.reactive import reactive
from textual.binding import Binding
from textual import events
from textual.messages import Message

from odoo_manager.core.instance import InstanceManager
from odoo_manager.core.database import DatabaseManager
from odoo_manager.core.module import ModuleManager
from odoo_manager.core.backup import BackupManager
from odoo_manager.core.monitor import HealthMonitor, HealthStatus
from odoo_manager.config import InstancesConfig


class AppState(str, Enum):
    """Application states."""

    INSTANCES = "instances"
    DATABASES = "databases"
    MODULES = "modules"
    BACKUPS = "backups"
    MONITOR = "monitor"
    LOGS = "logs"
    CONFIG = "config"


@dataclass
class InstanceInfo:
    """Information about an instance."""

    name: str
    version: str
    edition: str
    status: str
    running: bool
    port: int
    workers: int
    db_name: str
    cpu_percent: float = 0.0
    memory_mb: int = 0
    memory_percent: float = 0.0


class InstanceList(Container):
    """Widget displaying list of instances."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.instances: list[InstanceInfo] = []

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
                self.instances.append(
                    InstanceInfo(
                        name=inst.config.name,
                        version=inst.config.version,
                        edition=inst.config.edition,
                        status=inst.status(),
                        running=inst.is_running(),
                        port=inst.config.port,
                        workers=inst.config.workers,
                        db_name=inst.config.db_name,
                        cpu_percent=health.cpu_percent,
                        memory_mb=health.memory_mb,
                        memory_percent=health.memory_percent,
                    )
                )
        except Exception as e:
            self.instances = []

        self.update_table()

    def update_table(self) -> None:
        """Update the table with current data."""
        # Clear existing content
        self.remove_children()

        if not self.instances:
            self.mount(Placeholder(name="no_instances", text="No instances found"))
            return

        # Create table
        table = DataTable()
        table.add_column("Name", key="name")
        table.add_column("Status", key="status")
        table.add_column("Version", key="version")
        table.add_column("Port", key="port")
        table.add_column("CPU %", key="cpu")
        table.add_column("Mem %", key="memory")

        for inst in self.instances:
            status_style = "green" if inst.running else "red"
            status_text = Text(inst.status, style=status_style)
            cpu_text = Text(f"{inst.cpu_percent:.1f}", style="green" if inst.cpu_percent < 70 else "red")
            mem_text = Text(f"{inst.memory_percent:.1f}", style="green" if inst.memory_percent < 70 else "red")

            table.add_row(
                name=Text(inst.name, style="cyan bold"),
                status=status_text,
                version=Text(inst.version),
                port=str(inst.port),
                cpu=cpu_text,
                memory=mem_text,
            )

        self.mount(table)


class SideMenu(ListView):
    """Side navigation menu."""

    def __init__(self, **kwargs):
        items = [
            ListItem(Label("📦 Instances", id="instances")),
            ListItem(Label("💾 Databases", id="databases")),
            ListItem(Label("🧩 Modules", id="modules")),
            ListItem(Label("📋 Backups", id="backups")),
            ListItem(Label("📊 Monitor", id="monitor")),
            ListItem(Label("📜 Logs", id="logs")),
            ListItem(Label("⚙️  Config", id="config")),
        ]
        super().__init__(*items, **kwargs)


class StatusPanel(Container):
    """Status panel showing summary information."""

    total_instances = reactive(0)
    running_instances = reactive(0)
    stopped_instances = reactive(0)
    total_databases = reactive(0)
    system_cpu = reactive(0.0)
    system_memory = reactive(0.0)

    def watch_total_instances(self, old: int, new: int) -> None:
        """Update display when total instances changes."""
        self.query_one("#total_instances").update(str(new))

    def watch_running_instances(self, old: int, new: int) -> None:
        """Update display when running instances changes."""
        self.query_one("#running_instances").update(str(new))

    def watch_stopped_instances(self, old: int, new: int) -> None:
        """Update display when stopped instances changes."""
        self.query_one("#stopped_instances").update(str(new))

    def compose(self) -> ComposeResult:
        """Compose the status panel."""
        yield Static("📊 Dashboard", classes="panel-title")
        yield Horizontal(
            Static("Instances:"),
            Label("0", id="total_instances"),
        )
        yield Horizontal(
            Static("Running:"),
            Label("0", id="running_instances", style="green"),
        )
        yield Horizontal(
            Static("Stopped:"),
            Label("0", id="stopped_instances", style="red"),
        )
        yield Horizontal(
            Static("Databases:"),
            Label("0", id="total_databases"),
        )
        yield Horizontal(
            Static("CPU:"),
            Label("0%", id="system_cpu"),
        )
        yield Horizontal(
            Static("Memory:"),
            Label("0%", id="system_memory"),
        )

    def update_status(self) -> None:
        """Update status information."""
        try:
            import psutil

            manager = InstanceManager()
            instances = manager.list_instances()

            total = len(instances)
            running = sum(1 for i in instances if i.is_running())
            stopped = total - running

            self.total_instances = total
            self.running_instances = running
            self.stopped_instances = stopped

            # Count databases
            from odoo_manager.utils.postgres import list_databases

            try:
                databases = list_databases()
                self.query_one("#total_databases").update(str(len(databases)))
            except:
                pass

            # System stats
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory().percent

            self.query_one("#system_cpu").update(f"{cpu:.1f}%")
            cpu_style = "green" if cpu < 70 else "red" if cpu > 90 else "yellow"
            self.query_one("#system_cpu").style = cpu_style

            self.query_one("#system_memory").update(f"{memory:.1f}%")
            mem_style = "green" if memory < 70 else "red" if memory > 90 else "yellow"
            self.query_one("#system_memory").style = mem_style

        except Exception:
            pass


class LogPanel(Container):
    """Panel for displaying logs."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_instance: Optional[str] = None

    def compose(self) -> ComposeResult:
        """Compose the log panel."""
        yield Static("📜 Logs", classes="panel-title")
        yield Log(id="log_output", auto_scroll=True, highlight=True)

    def load_logs(self, instance_name: str, tail: int = 100) -> None:
        """Load logs for an instance."""
        try:
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)
            logs = instance.get_logs(follow=False, tail=tail)

            log_widget = self.query_one("#log_output", Log)
            log_widget.clear()
            log_widget.write(logs)

            self.current_instance = instance_name
        except Exception as e:
            log_widget = self.query_one("#log_output", Log)
            log_widget.write(f"Error loading logs: {e}")


class ActionPanel(Container):
    """Panel with action buttons."""

    def compose(self) -> ComposeResult:
        """Compose the action panel."""
        yield Static("⚡ Actions", classes="panel-title")
        yield Button("🔄 Refresh", id="btn_refresh", variant="primary")
        yield Button("▶️  Start", id="btn_start", variant="success")
        yield Button("⏸️  Stop", id="btn_stop", variant="error")
        yield Button("🔄 Restart", id="btn_restart", variant="warning")
        yield Button("🗑️  Remove", id="btn_remove", variant="error")
        yield Button("📜 Logs", id="btn_logs")
        yield Button("🐚 Shell", id="btn_shell")


class DetailPanel(Container):
    """Panel showing details of selected item."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_instance: Optional[InstanceInfo] = None

    def compose(self) -> ComposeResult:
        """Compose the detail panel."""
        yield Static("📋 Details", classes="panel-title")
        yield Static(id="detail_content")

    def show_instance(self, instance: InstanceInfo) -> None:
        """Show instance details."""
        self.current_instance = instance

        content = self.query_one("#detail_content", Static)
        content.update(
            f"""[bold cyan]Name:[/bold cyan] {instance.name}
[bold]Version:[/bold] {instance.version}
[bold]Edition:[/bold] {instance.edition}
[bold]Status:[/bold] {'✓ Running' if instance.running else '✗ Stopped'}
[bold]Port:[/bold] {instance.port}
[bold]Workers:[/bold] {instance.workers}
[bold]Database:[/bold] {instance.db_name}
[bold]CPU:[/bold] {instance.cpu_percent:.1f}%
[bold]Memory:[/bold] {instance.memory_mb} MB ({instance.memory_percent:.1f}%)
"""
        )


class OdooManagerTUI(App):
    """Main TUI application for Odoo Manager."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #header {
        background: $primary;
        text-style: bold;
    }

    #side_menu {
        width: 25;
        background: $surface;
    }

    #status_panel {
        width: 30;
        background: $surface;
        padding: 1;
    }

    #main_content {
        height: 1fr;
    }

    #instance_list {
        height: 1fr;
    }

    #detail_panel {
        width: 40;
        background: $surface;
        padding: 1;
    }

    #action_panel {
        width: 25;
        background: $surface;
        padding: 1;
    }

    #log_panel {
        height: 1fr;
        background: $panel;
    }

    .panel-title {
        text-style: bold;
        margin-bottom: 1;
    }

    Button {
        margin: 1 0;
    }

    DataTable {
        height: 1fr;
    }
    """

    TITLE = "Odoo Manager"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "start", "Start instance"),
        Binding("t", "stop", "Stop instance"),
        Binding("R", "restart", "Restart instance"),
        Binding("l", "logs", "View logs"),
        Binding("tab", "focus_next", "Focus next"),
        Binding("shift+tab", "focus_previous", "Focus previous"),
    ]

    current_state: AppState = AppState.INSTANCES
    selected_instance: Optional[InstanceInfo] = None

    def compose(self) -> ComposeResult:
        """Compose the application."""
        yield Header()
        yield Horizontal(
            SideMenu(id="side_menu"),
            Container(id="main_content"),
            StatusPanel(id="status_panel"),
            DetailPanel(id="detail_panel"),
            ActionPanel(id="action_panel"),
        )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize on mount."""
        self.show_instances()
        self.update_status()

    def show_instances(self) -> None:
        """Show instances view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(InstanceList(id="instance_list"))
        self.current_state = AppState.INSTANCES

    def update_status(self) -> None:
        """Update status panel."""
        status_panel = self.query_one("#status_panel", StatusPanel)
        if status_panel:
            status_panel.update_status()

    def action_refresh(self) -> None:
        """Refresh all data."""
        instance_list = self.query_one("#instance_list", InstanceList)
        if instance_list:
            instance_list.refresh_instances()

        self.update_status()

    def action_start(self) -> None:
        """Start selected instance."""
        if self.selected_instance:
            try:
                manager = InstanceManager()
                instance = manager.get_instance(self.selected_instance.name)
                instance.start()
                self.action_refresh()
                self.notify(f"Started {self.selected_instance.name}", severity="information")
            except Exception as e:
                self.notify(f"Failed to start: {e}", severity="error")

    def action_stop(self) -> None:
        """Stop selected instance."""
        if self.selected_instance:
            try:
                manager = InstanceManager()
                instance = manager.get_instance(self.selected_instance.name)
                instance.stop()
                self.action_refresh()
                self.notify(f"Stopped {self.selected_instance.name}", severity="information")
            except Exception as e:
                self.notify(f"Failed to stop: {e}", severity="error")

    def action_restart(self) -> None:
        """Restart selected instance."""
        if self.selected_instance:
            try:
                manager = InstanceManager()
                instance = manager.get_instance(self.selected_instance.name)
                instance.restart()
                self.action_refresh()
                self.notify(f"Restarted {self.selected_instance.name}", severity="information")
            except Exception as e:
                self.notify(f"Failed to restart: {e}", severity="error")

    def action_logs(self) -> None:
        """Show logs for selected instance."""
        if self.selected_instance:
            main_content = self.query_one("#main_content", Container)
            main_content.remove_children()
            log_panel = LogPanel(id="log_panel")
            main_content.mount(log_panel)
            log_panel.load_logs(self.selected_instance.name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        button_id = event.button.id

        if button_id == "btn_refresh":
            self.action_refresh()
        elif button_id == "btn_start":
            self.action_start()
        elif button_id == "btn_stop":
            self.action_stop()
        elif button_id == "btn_restart":
            self.action_restart()
        elif button_id == "btn_logs":
            self.action_logs()
        elif button_id == "btn_shell":
            if self.selected_instance:
                self.notify(f"Opening shell for {self.selected_instance.name}...", severity="information")
                # Exit TUI and open shell
                self.exit(return_code=0)
                import subprocess
                subprocess.run(["odoo-manager", "ssh", "shell", self.selected_instance.name])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle menu selection."""
        if event.item.id == "instances":
            self.show_instances()
        elif event.item.id == "monitor":
            # Could add monitoring view
            pass
        # Add more menu items as needed


def launch_tui():
    """Launch the TUI application."""
    app = OdooManagerTUI()
    app.run()
