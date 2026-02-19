"""
Terminal User Interface (TUI) for Odoo Manager using Textual.

A beautiful, user-friendly interface where most operations are done by selection
rather than typing. Minimal text input only when necessary.
"""

from dataclasses import dataclass
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
    Log,
    Switch,
    Select,
)
from textual.binding import Binding
from textual.screen import ModalScreen
from textual import on

from odoo_manager.core.instance import InstanceManager
from odoo_manager.core.monitor import HealthMonitor
from odoo_manager.config import Config


class AppState(str, Enum):
    """Application states."""
    DASHBOARD = "dashboard"
    INSTANCES = "instances"
    DATABASES = "databases"
    MODULES = "modules"
    BACKUPS = "backups"
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


class StatCard(Container):
    """A stat card widget for displaying metrics."""

    def __init__(self, title: str, value_id: str, color: str, **kwargs):
        super().__init__(classes=f"stat-card stat-{color}", **kwargs)
        self.title = title
        self.value_id = value_id
        self.color = color

    def compose(self) -> ComposeResult:
        """Compose the stat card."""
        yield Static(self.title, classes="stat-title")
        yield Static("0", id=self.value_id, classes="stat-value")


class Dashboard(Container):
    """Main dashboard with stats and quick actions."""

    def on_mount(self) -> None:
        """Load stats when mounted."""
        self.update_stats()

    def update_stats(self) -> None:
        """Update dashboard statistics."""
        try:
            import psutil

            manager = InstanceManager()
            instances = manager.list_instances()

            total = len(instances)
            running = sum(1 for i in instances if i.is_running())
            stopped = total - running

            # Update counts
            self.query_one("#total_instances", Static).update(str(total))
            self.query_one("#running_instances", Static).update(str(running))
            self.query_one("#stopped_instances", Static).update(str(stopped))

            # System stats
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory().percent

            cpu_style = "green" if cpu < 70 else "yellow" if cpu < 90 else "red"
            cpu_label = self.query_one("#system_cpu", Static)
            cpu_label.update(Text(f"{cpu:.1f}%", style=cpu_style))

            mem_style = "green" if memory < 70 else "yellow" if memory < 90 else "red"
            mem_label = self.query_one("#system_memory", Static)
            mem_label.update(Text(f"{memory:.1f}%", style=mem_style))

        except Exception:
            pass

    def compose(self) -> ComposeResult:
        """Compose the dashboard."""
        yield Static("[bold]System Overview[/]", classes="header-text")

        # Stats cards
        with Vertical(id="stats_container"):
            with Horizontal(classes="stat-row"):
                yield StatCard("Instances", "total_instances", "cyan")
                yield StatCard("Running", "running_instances", "green")
                yield StatCard("Stopped", "stopped_instances", "red")
            with Horizontal(classes="stat-row"):
                yield StatCard("CPU", "system_cpu", "yellow")
                yield StatCard("Memory", "system_memory", "yellow")

        yield Static("[bold]Quick Actions[/]", classes="header-text")
        with Horizontal(classes="actions-row"):
            yield Button("New Instance", id="btn_new_instance", variant="primary")
            yield Button("Refresh", id="btn_refresh_all")


class InstanceTable(Container):
    """Widget displaying list of instances with actions."""

    instances: list[InstanceInfo] = []

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
        except Exception:
            self.instances = []

        self.update_table()

    def update_table(self) -> None:
        """Update the table with current data."""
        table = self.query_one(DataTable)
        table.clear()

        if not self.instances:
            table.add_row(
                Text("No instances found", style="dim italic"),
                "", "", "", "", ""
            )
            return

        for inst in self.instances:
            status_icon = "[green]ON[/green]" if inst.running else "[red]OFF[/red]"
            status_text = Text(status_icon, style="default")

            cpu_style = "green" if inst.cpu_percent < 70 else "yellow" if inst.cpu_percent < 90 else "red"
            cpu_text = Text(f"{inst.cpu_percent:.1f}%", style=cpu_style)

            mem_style = "green" if inst.memory_percent < 70 else "yellow" if inst.memory_percent < 90 else "red"
            mem_text = Text(f"{inst.memory_percent:.1f}%", style=mem_style)

            table.add_row(
                Text(inst.name, style="cyan bold"),
                status_text,
                Text(inst.version),
                Text(str(inst.port)),
                cpu_text,
                mem_text,
            )

    def compose(self) -> ComposeResult:
        """Compose the instance table."""
        yield Static("[bold]Odoo Instances[/]", classes="header-text")
        table = DataTable(id="instance_table")
        table.add_column("Name", key="name", width=20)
        table.add_column("Status", key="status", width=15)
        table.add_column("Version", key="version", width=10)
        table.add_column("Port", key="port", width=8)
        table.add_column("CPU", key="cpu", width=10)
        table.add_column("Memory", key="memory", width=10)
        table.cursor_type = "row"
        yield table

        with Horizontal(classes="table-actions"):
            yield Button("Create New", id="btn_create_instance", variant="primary")
            yield Button("Refresh", id="btn_refresh_instances")


class CreateInstanceScreen(ModalScreen):
    """Screen for creating a new instance."""

    DEFAULT_CSS = """
    CreateInstanceScreen {
        align: center middle;
    }

    #create_dialog {
        width: 60;
        height: 25;
        background: $panel;
        border: thick $primary;
    }

    .form-row {
        height: 3;
        padding: 0 2;
    }

    .form-label {
        width: 15;
        text-align: right;
        padding: 1 2;
    }

    .small-input {
        width: 20;
    }

    .actions {
        height: 3;
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the create instance form."""
        with Container(id="create_dialog"):
            yield Static("[bold]Create New Instance[/]", classes="header-text")

            # Instance name
            with Horizontal(classes="form-row"):
                yield Label("Name:", classes="form-label")
                yield Input(placeholder="my-odoo", id="input_name", classes="small-input")

            # Version
            with Horizontal(classes="form-row"):
                yield Label("Version:", classes="form-label")
                yield Select(
                    [
                        ("19.0", "19.0"),
                        ("18.0", "18.0"),
                        ("17.0", "17.0"),
                        ("16.0", "16.0"),
                        ("master", "master"),
                    ],
                    id="input_version",
                    value="19.0",
                    allow_blank=False,
                )

            # Edition
            with Horizontal(classes="form-row"):
                yield Label("Edition:", classes="form-label")
                yield Select(
                    [
                        ("Community", "community"),
                        ("Enterprise", "enterprise"),
                    ],
                    id="input_edition",
                    value="community",
                    allow_blank=False,
                )

            # Port
            with Horizontal(classes="form-row"):
                yield Label("Port:", classes="form-label")
                yield Select(
                    [
                        ("8069 (Default)", "8069"),
                        ("8070", "8070"),
                        ("8071", "8071"),
                        ("8072", "8072"),
                    ],
                    id="input_port",
                    value="8069",
                    allow_blank=False,
                )

            # Workers
            with Horizontal(classes="form-row"):
                yield Label("Workers:", classes="form-label")
                yield Select(
                    [
                        ("2", "2"),
                        ("4 (Recommended)", "4"),
                        ("8", "8"),
                    ],
                    id="input_workers",
                    value="4",
                    allow_blank=False,
                )

            with Horizontal(classes="actions"):
                yield Button("Create", id="btn_do_create", variant="primary")
                yield Button("Cancel", id="btn_cancel_create")

    @on(Button.Pressed, "#btn_cancel_create")
    def on_cancel(self) -> None:
        """Cancel and close dialog."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn_do_create")
    def on_create(self) -> None:
        """Create the instance."""
        try:
            name = self.query_one("#input_name", Input).value.strip()
            version = self.query_one("#input_version", Select).value
            edition = self.query_one("#input_edition", Select).value
            port = int(self.query_one("#input_port", Select).value)
            workers = int(self.query_one("#input_workers", Select).value)

            if not name:
                self.app.notify("Please enter an instance name", severity="error")
                return

            manager = InstanceManager()
            manager.create_instance(
                name=name,
                version=version,
                edition=edition,
                port=port,
                workers=workers,
                deployment_type="docker",
            )

            self.app.notify(f"Instance '{name}' created!", severity="information")
            self.app.pop_screen()

            # Refresh the instance list
            if hasattr(self.app, "refresh_instances"):
                self.app.refresh_instances()

        except Exception as e:
            self.app.notify(f"Failed: {e}", severity="error")


class ActionDialog(ModalScreen):
    """Dialog for instance actions."""

    DEFAULT_CSS = """
    ActionDialog {
        align: center middle;
    }

    #action_dialog {
        width: 50;
        height: 15;
        background: $panel;
        border: thick $primary;
    }
    """

    def __init__(self, title: str, action: str, instance_name: str, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.action = action
        self.instance_name = instance_name

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Container(id="action_dialog"):
            yield Static(self.title, classes="header-text")
            yield Static(f"Confirm this action for '{self.instance_name}'?")
            with Horizontal(classes="actions"):
                yield Button("Confirm", id="btn_confirm", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

    @on(Button.Pressed, "#btn_cancel")
    def on_cancel(self) -> None:
        """Cancel dialog."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn_confirm")
    def on_confirm(self) -> None:
        """Execute the action."""
        try:
            manager = InstanceManager()
            instance = manager.get_instance(self.instance_name)

            if self.action == "start":
                instance.start()
                self.app.notify(f"Started '{self.instance_name}'")
            elif self.action == "stop":
                instance.stop()
                self.app.notify(f"Stopped '{self.instance_name}'")
            elif self.action == "restart":
                instance.restart()
                self.app.notify(f"Restarted '{self.instance_name}'")
            elif self.action == "remove":
                instance.remove()
                manager.remove_instance(self.instance_name)
                self.app.notify(f"Removed '{self.instance_name}'")

            self.app.pop_screen()

            if hasattr(self.app, "refresh_instances"):
                self.app.refresh_instances()

        except Exception as e:
            self.app.notify(f"Action failed: {e}", severity="error")


class OdooManagerTUI(App):
    """Main TUI application for Odoo Manager."""

    CSS = """
    Screen {
        background: $background;
    }

    #nav_sidebar {
        width: 28;
        background: $surface;
        dock: left;
    }

    #main_content {
        height: 1fr;
    }

    .header-text {
        text-style: bold;
        text-align: center;
        padding: 1 0;
        border-bottom: solid $primary;
        margin-bottom: 1;
    }

    #stats_container {
        height: 12;
        margin: 1 0;
    }

    .stat-row {
        height: 6;
    }

    .stat-card {
        width: 1fr;
        height: 1fr;
        background: $panel;
        border: round $primary;
        padding: 1;
        margin: 0 1;
        content-align: center middle;
    }

    .stat-card.stat-cyan {
        border: round cyan;
    }

    .stat-card.stat-green {
        border: round green;
    }

    .stat-card.stat-red {
        border: round red;
    }

    .stat-card.stat-yellow {
        border: round yellow;
    }

    .stat-title {
        text-style: bold dim;
        margin-bottom: 1;
    }

    .stat-value {
        text-style: bold;
    }

    .actions-row {
        height: 3;
        align: center middle;
        padding: 1 0;
    }

    .table-actions {
        height: 3;
        align: center middle;
        padding: 1 0;
    }

    Button {
        margin: 0 1;
    }

    DataTable {
        height: 1fr;
    }
    """

    TITLE = "Odoo Manager"
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("n", "new_instance", "New", show=True),
        Binding("tab", "focus_next", "Next", show=False),
        Binding("shift+tab", "focus_previous", "Previous", show=False),
        Binding("up", "focus_previous", "Up", show=False),
        Binding("down", "focus_next", "Down", show=False),
    ]

    current_state: AppState = AppState.DASHBOARD

    def compose(self) -> ComposeResult:
        """Compose the application."""
        yield Header()

        # Navigation sidebar
        with Vertical(id="nav_sidebar"):
            yield Static("[bold]Navigation[/]", classes="header-text")
            yield Button("Dashboard", id="nav_dashboard", variant="primary")
            yield Button("Instances", id="nav_instances")
            yield Button("Databases", id="nav_databases")
            yield Button("Modules", id="nav_modules")
            yield Button("Backups", id="nav_backups")
            yield Button("Logs", id="nav_logs")
            yield Button("Config", id="nav_config")

        # Main content
        yield Container(id="main_content")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize on mount."""
        self.show_dashboard()

    # Navigation button handlers
    @on(Button.Pressed, "#nav_dashboard")
    def show_dashboard(self) -> None:
        """Show dashboard view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(Dashboard(id="dashboard"))
        self.current_state = AppState.DASHBOARD
        self._update_nav_highlight("nav_dashboard")

    @on(Button.Pressed, "#nav_instances")
    def show_instances(self) -> None:
        """Show instances view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(InstanceTable(id="instances"))
        self.current_state = AppState.INSTANCES
        self._update_nav_highlight("nav_instances")

    @on(Button.Pressed, "#nav_databases")
    def show_databases(self) -> None:
        """Show databases view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(Static("[bold]Database Management[/]\n\nComing soon..."))
        self.current_state = AppState.DATABASES
        self._update_nav_highlight("nav_databases")

    @on(Button.Pressed, "#nav_modules")
    def show_modules(self) -> None:
        """Show modules view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(Static("[bold]Module Management[/]\n\nComing soon..."))
        self.current_state = AppState.MODULES
        self._update_nav_highlight("nav_modules")

    @on(Button.Pressed, "#nav_backups")
    def show_backups(self) -> None:
        """Show backups view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(Static("[bold]Backup Management[/]\n\nComing soon..."))
        self.current_state = AppState.BACKUPS
        self._update_nav_highlight("nav_backups")

    @on(Button.Pressed, "#nav_logs")
    def show_logs(self) -> None:
        """Show logs view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(Static("[bold]Log Viewer[/]\n\nComing soon..."))
        self.current_state = AppState.LOGS
        self._update_nav_highlight("nav_logs")

    @on(Button.Pressed, "#nav_config")
    def show_config(self) -> None:
        """Show config view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(Static("[bold]Configuration[/]\n\nComing soon..."))
        self.current_state = AppState.CONFIG
        self._update_nav_highlight("nav_config")

    # Action button handlers
    @on(Button.Pressed, "#btn_new_instance")
    @on(Button.Pressed, "#btn_create_instance")
    def action_new_instance(self) -> None:
        """Show create instance dialog."""
        self.push_screen(CreateInstanceScreen())

    @on(Button.Pressed, "#btn_refresh_all")
    @on(Button.Pressed, "#btn_refresh_instances")
    def refresh_instances(self) -> None:
        """Refresh instances."""
        if self.current_state == AppState.INSTANCES:
            try:
                instances = self.query_one(InstanceTable)
                instances.refresh_instances()
            except:
                pass
        elif self.current_state == AppState.DASHBOARD:
            try:
                dashboard = self.query_one(Dashboard)
                dashboard.update_stats()
            except:
                pass

    def action_refresh(self) -> None:
        """Refresh current view (for binding)."""
        self.refresh_instances()

    def _update_nav_highlight(self, selected_id: str) -> None:
        """Update navigation button highlights."""
        nav_ids = ["nav_dashboard", "nav_instances", "nav_databases",
                   "nav_modules", "nav_backups", "nav_logs", "nav_config"]
        for nav_id in nav_ids:
            try:
                btn = self.query_one(f"#{nav_id}", Button)
                if nav_id == selected_id:
                    btn.variant = "primary"
                else:
                    btn.variant = "default"
            except:
                pass


def launch_tui():
    """Launch the TUI application."""
    app = OdooManagerTUI()
    app.run()
