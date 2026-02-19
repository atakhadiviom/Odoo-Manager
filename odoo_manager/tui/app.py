"""
Terminal User Interface (TUI) for Odoo Manager using Textual.

A beautiful, user-friendly interface where most operations are done by selection
rather than typing. Minimal text input only when necessary.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import subprocess

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
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
    Log,
    Switch,
    Select,
    SelectionList,
    Markdown,
)
from textual.reactive import reactive
from textual.binding import Binding
from textual import events
from textual.screen import ModalScreen
from textual import on
from textual.widgets import Checkbox

from odoo_manager.core.instance import InstanceManager
from odoo_manager.core.database import DatabaseManager
from odoo_manager.core.module import ModuleManager
from odoo_manager.core.backup import BackupManager
from odoo_manager.core.monitor import HealthMonitor, HealthStatus
from odoo_manager.config import InstancesConfig, Config
from odoo_manager.constants import (
    DEFAULT_ODOO_PORT,
    DEFAULT_ODOO_WORKERS,
    DEFAULT_ODOO_VERSION,
    EDITION_COMMUNITY,
    EDITION_ENTERPRISE,
    STATE_RUNNING,
    STATE_STOPPED,
)


class AppState(str, Enum):
    """Application states."""

    DASHBOARD = "dashboard"
    INSTANCES = "instances"
    DATABASES = "databases"
    MODULES = "modules"
    BACKUPS = "backups"
    MONITOR = "monitor"
    LOGS = "logs"
    CONFIG = "config"
    CREATE_INSTANCE = "create_instance"


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

    def __init__(self, title: str, value: str, value_id: str, color: str, **kwargs):
        super().__init__(classes=f"stat-card stat-{color}", **kwargs)
        self.title = title
        self.value = value
        self.value_id = value_id
        self.color = color

    def compose(self) -> ComposeResult:
        """Compose the stat card."""
        yield Static(self.title, classes="stat-title")
        yield Static(self.value, id=self.value_id, classes="stat-value")


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
        yield Static("📊 System Overview", classes="header-text")

        # Stats cards
        with Vertical(id="stats_container"):
            with Horizontal(classes="stat-row"):
                yield StatCard("📦 Instances", "0", "total_instances", "cyan")
                yield StatCard("▶️  Running", "0", "running_instances", "green")
                yield StatCard("⏸️  Stopped", "0", "stopped_instances", "red")
            with Horizontal(classes="stat-row"):
                yield StatCard("💾 CPU", "0%", "system_cpu", "yellow")
                yield StatCard("🧠 Memory", "0%", "system_memory", "yellow")

        yield Static("⚡ Quick Actions", classes="header-text")
        with Horizontal(classes="actions-row"):
            yield Button("➕ New Instance", id="btn_new_instance", variant="primary")
            yield Button("🔄 Refresh All", id="btn_refresh_all", variant="default")
            yield Button("📋 View Logs", id="btn_view_logs", variant="default")

        yield Static("📝 Recent Activity", classes="header-text")
        yield Static("No recent activity", id="recent_activity", classes="dim-text")


class InstanceTable(Container):
    """Widget displaying list of instances with actions."""

    instances: list[InstanceInfo] = []
    selected_instance: Optional[InstanceInfo] = None

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
            status_icon = "🟢" if inst.running else "🔴"
            status_text = Text(f"{status_icon} {inst.status}", style="green" if inst.running else "red")

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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        if event.row_key and self.instances:
            idx = event.row_key.key if isinstance(event.row_key.key, int) else 0
            if 0 <= idx < len(self.instances):
                self.selected_instance = self.instances[idx]
                self.app.show_instance_actions(self.selected_instance)

    def compose(self) -> ComposeResult:
        """Compose the instance table."""
        yield Static("📦 Odoo Instances", classes="header-text")
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
            yield Button("➕ Create New", id="btn_create_instance", variant="primary")
            yield Button("🔄 Refresh", id="btn_refresh_instances")
            yield Button("📊 Monitor", id="btn_monitor_all")


class DatabaseManagerUI(Container):
    """Database management interface."""

    current_instance: Optional[str] = None

    def compose(self) -> ComposeResult:
        """Compose the database manager."""
        yield Static("💾 Database Management", classes="header-text")

        # Instance selector
        with Horizontal(classes="form-row"):
            yield Label("Instance:", classes="form-label")
            yield Select(
                [],
                id="db_instance_select",
                prompt="Select an instance...",
                allow_blank=False,
            )
            yield Button("🔄 Load", id="btn_load_databases")

        # Database list
        yield Static("Databases:", classes="subheader-text")
        table = DataTable(id="database_table")
        table.add_column("Database", key="name", width=30)
        table.add_column("Size", key="size", width=15)
        table.add_column("Owner", key="owner", width=15)
        yield table

        # Actions
        with Horizontal(classes="actions-row"):
            yield Button("➕ New Database", id="btn_create_db", variant="primary")
            yield Button("📋 Backup", id="btn_backup_db")
            yield Button("♻️  Duplicate", id="btn_duplicate_db")
            yield Button("🗑️  Drop", id="btn_drop_db", variant="error")

    def on_mount(self) -> None:
        """Load instance list on mount."""
        self._load_instances()

    def _load_instances(self) -> None:
        """Populate instance selector."""
        try:
            manager = InstanceManager()
            instances = manager.list_instances()
            options = [(str(inst.config.name), inst.config.name) for inst in instances]
            select = self.query_one("#db_instance_select", Select)
            select.set_options(options)
            if options:
                select.select_option(options[0][1])
        except Exception:
            pass


class ModuleManagerUI(Container):
    """Module management interface."""

    def compose(self) -> ComposeResult:
        """Compose the module manager."""
        yield Static("🧩 Module Management", classes="header-text")

        # Instance selector
        with Horizontal(classes="form-row"):
            yield Label("Instance:", classes="form-label")
            yield Select(
                [],
                id="module_instance_select",
                prompt="Select an instance...",
                allow_blank=False,
            )
            yield Button("🔄 Load Modules", id="btn_load_modules")

        # Filter tabs
        yield Static("Filter:", classes="subheader-text")
        with Horizontal(classes="filter-row"):
            yield Button("All", id="btn_filter_all", variant="primary")
            yield Button("Installed", id="btn_filter_installed")
            yield Button("Not Installed", id="btn_filter_uninstalled")
            yield Button("To Upgrade", id="btn_filter_upgrade")

        # Module list with selection
        yield Static("Modules (use Space to select):", classes="subheader-text")
        list_widget = SelectionList(id="module_list")
        yield list_widget

        # Actions
        with Horizontal(classes="actions-row"):
            yield Button("✓ Install Selected", id="btn_install_modules", variant="primary")
            yield Button("✗ Uninstall", id="btn_uninstall_modules")
            yield Button("🔄 Update", id="btn_update_modules")
            yield Button("🔄 Update All", id="btn_update_all_modules")


class BackupManagerUI(Container):
    """Backup management interface."""

    def compose(self) -> ComposeResult:
        """Compose the backup manager."""
        yield Static("📋 Backup Management", classes="header-text")

        # Instance selector
        with Horizontal(classes="form-row"):
            yield Label("Instance:", classes="form-label")
            yield Select(
                [],
                id="backup_instance_select",
                prompt="Select an instance...",
                allow_blank=False,
            )
            yield Button("💾 Create Backup", id="btn_create_backup", variant="primary")

        # Backup list
        yield Static("Available Backups:", classes="subheader-text")
        table = DataTable(id="backup_table")
        table.add_column("Name", key="name", width=30)
        table.add_column("Date", key="date", width=20)
        table.add_column("Size", key="size", width=15)
        table.add_column("Type", key="type", width=10)
        yield table

        # Actions
        with Horizontal(classes="actions-row"):
            yield Button("♻️  Restore", id="btn_restore_backup")
            yield Button("📥 Download", id="btn_download_backup")
            yield Button("🗑️  Delete", id="btn_delete_backup", variant="error")


class LogViewer(Container):
    """Log viewing interface."""

    current_instance: Optional[str] = None

    def compose(self) -> ComposeResult:
        """Compose the log viewer."""
        yield Static("📜 Log Viewer", classes="header-text")

        # Controls
        with Horizontal(classes="form-row"):
            yield Label("Instance:", classes="form-label")
            yield Select(
                [],
                id="log_instance_select",
                prompt="Select an instance...",
                allow_blank=False,
            )
            yield Label("Lines:", classes="form-label")
            yield Input(value="100", placeholder="100", id="log_lines", classes="small-input")
            yield Button("🔄 Load", id="btn_load_logs")
            yield Switch(value=False, id="log_follow", label="Follow")

        # Log output
        log_widget = Log(id="log_output", auto_scroll=True, highlight=True, wrap=True)
        yield log_widget

        # Actions
        with Horizontal(classes="actions-row"):
            yield Button("📋 Copy", id="btn_copy_logs")
            yield Button("🔍 Search", id="btn_search_logs")
            yield Button("🗑️  Clear", id="btn_clear_logs")

    def on_mount(self) -> None:
        """Load instance list on mount."""
        self._load_instances()

    def _load_instances(self) -> None:
        """Populate instance selector."""
        try:
            manager = InstanceManager()
            instances = manager.list_instances()
            options = [(str(inst.config.name), inst.config.name) for inst in instances]
            select = self.query_one("#log_instance_select", Select)
            select.set_options(options)
            if options:
                select.select_option(options[0][1])
        except Exception:
            pass


class CreateInstanceScreen(ModalScreen):
    """Screen for creating a new instance with form-based input."""

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
            yield Static("➕ Create New Instance", classes="header-text")

            # Instance name (text input required)
            with Horizontal(classes="form-row"):
                yield Label("Name:", classes="form-label")
                yield Input(placeholder="my-odoo", id="input_name", classes="small-input")

            # Version (dropdown)
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

            # Edition (dropdown)
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

            # Port (dropdown with common options)
            with Horizontal(classes="form-row"):
                yield Label("Port:", classes="form-label")
                yield Select(
                    [
                        ("8069 (Default)", "8069"),
                        ("8070", "8070"),
                        ("8071", "8071"),
                        ("8072", "8072"),
                        ("8073", "8073"),
                    ],
                    id="input_port",
                    value="8069",
                    allow_blank=False,
                )

            # Workers (dropdown)
            with Horizontal(classes="form-row"):
                yield Label("Workers:", classes="form-label")
                yield Select(
                    [
                        ("2", "2"),
                        ("4 (Recommended)", "4"),
                        ("8", "8"),
                        ("16", "16"),
                    ],
                    id="input_workers",
                    value="4",
                    allow_blank=False,
                )

            # Deployment type
            with Horizontal(classes="form-row"):
                yield Label("Deployment:", classes="form-label")
                yield Select(
                    [
                        ("Docker (Recommended)", "docker"),
                        ("Source", "source"),
                    ],
                    id="input_deployment",
                    value="docker",
                    allow_blank=False,
                )

            with Horizontal(classes="actions"):
                yield Button("✓ Create", id="btn_do_create", variant="primary")
                yield Button("✗ Cancel", id="btn_cancel_create")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn_cancel_create":
            self.app.pop_screen()
        elif event.button.id == "btn_do_create":
            self._create_instance()

    def _create_instance(self) -> None:
        """Create the instance with form values."""
        try:
            name = self.query_one("#input_name", Input).value.strip()
            version = self.query_one("#input_version", Select).value
            edition = self.query_one("#input_edition", Select).value
            port = int(self.query_one("#input_port", Select).value)
            workers = int(self.query_one("#input_workers", Select).value)
            deployment = self.query_one("#input_deployment", Select).value

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
                deployment_type=deployment,
            )

            self.app.notify(f"Instance '{name}' created successfully!", severity="information")
            self.app.pop_screen()

            # Refresh the instance list
            if hasattr(self.app, "refresh_instances"):
                self.app.refresh_instances()

        except Exception as e:
            self.app.notify(f"Failed to create instance: {e}", severity="error")


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

    def __init__(self, title: str, message: str, action: str, instance_name: str, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.message = message
        self.action = action
        self.instance_name = instance_name

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Container(id="action_dialog"):
            yield Static(self.title, classes="header-text")
            yield Static(self.message, classes="dialog-message")
            with Horizontal(classes="actions"):
                yield Button("✓ Confirm", id="btn_confirm", variant="primary")
                yield Button("✗ Cancel", id="btn_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn_cancel":
            self.app.pop_screen()
        elif event.button.id == "btn_confirm":
            self._execute_action()

    def _execute_action(self) -> None:
        """Execute the confirmed action."""
        try:
            manager = InstanceManager()
            instance = manager.get_instance(self.instance_name)

            if self.action == "start":
                instance.start()
                self.app.notify(f"Started '{self.instance_name}'", severity="information")
            elif self.action == "stop":
                instance.stop()
                self.app.notify(f"Stopped '{self.instance_name}'", severity="information")
            elif self.action == "restart":
                instance.restart()
                self.app.notify(f"Restarted '{self.instance_name}'", severity="information")
            elif self.action == "remove":
                instance.remove()
                manager.remove_instance(self.instance_name)
                self.app.notify(f"Removed '{self.instance_name}'", severity="information")

            self.app.pop_screen()

            # Refresh if available
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

    /* Header styling */
    #header {
        background: $primary;
        text-style: bold;
    }

    /* Navigation sidebar */
    #nav_sidebar {
        width: 28;
        background: $surface;
        dock: left;
    }

    /* Main content area */
    #main_content {
        height: 1fr;
    }

    /* Text styles */
    .header-text {
        text-style: bold;
        text-align: center;
        padding: 1 0;
        border-bottom: solid $primary;
        margin-bottom: 1;
    }

    .subheader-text {
        text-style: bold;
        padding: 1 0;
        dim: false;
    }

    .dim-text {
        text-style: dim;
        text-align: center;
        padding: 2 0;
    }

    /* Stat cards */
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
        font-size: 200%;
    }

    /* Action buttons */
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

    .form-row {
        height: 3;
        padding: 0 1;
    }

    .form-label {
        width: 12;
        text-align: right;
        padding: 1 1;
        text-style: bold;
    }

    .small-input {
        width: 25;
    }

    .filter-row {
        height: 3;
    }

    /* Tables */
    DataTable {
        height: 1fr;
    }

    /* Selection List */
    SelectionList {
        height: 1fr;
    }

    /* Log output */
    #log_output {
        height: 1fr;
        border: round $primary;
    }

    /* Buttons */
    Button {
        margin: 0 1;
    }

    /* Nav items */
    .nav-item {
        padding: 1 2;
        text-style: bold;
    }

    .nav-item-selected {
        background: $primary;
        text-style: bold reverse;
    }
    """

    TITLE = "Odoo Manager"
    SUB_TITLE = "Manage your Odoo instances"
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("n", "new_instance", "New Instance", show=True),
        Binding("tab", "focus_next", "Next", show=False),
        Binding("shift+tab", "focus_previous", "Previous", show=False),
    ]

    current_state: AppState = AppState.DASHBOARD

    def compose(self) -> ComposeResult:
        """Compose the application."""
        yield Header()

        # Navigation sidebar
        with Vertical(id="nav_sidebar"):
            yield Static("📋 Navigation", classes="header-text")
            yield Button("📊 Dashboard", id="nav_dashboard", variant="primary")
            yield Button("📦 Instances", id="nav_instances")
            yield Button("💾 Databases", id="nav_databases")
            yield Button("🧩 Modules", id="nav_modules")
            yield Button("📋 Backups", id="nav_backups")
            yield Button("📜 Logs", id="nav_logs")
            yield Button("⚙️  Config", id="nav_config")

        # Main content
        yield Container(id="main_content")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize on mount."""
        self.show_dashboard()

    def show_dashboard(self) -> None:
        """Show dashboard view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(Dashboard(id="dashboard"))
        self.current_state = AppState.DASHBOARD
        self._update_nav_highlight("nav_dashboard")

    def show_instances(self) -> None:
        """Show instances view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(InstanceTable(id="instances"))
        self.current_state = AppState.INSTANCES
        self._update_nav_highlight("nav_instances")

    def show_databases(self) -> None:
        """Show databases view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(DatabaseManagerUI(id="databases"))
        self.current_state = AppState.DATABASES
        self._update_nav_highlight("nav_databases")

    def show_modules(self) -> None:
        """Show modules view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(ModuleManagerUI(id="modules"))
        self.current_state = AppState.MODULES
        self._update_nav_highlight("nav_modules")

    def show_backups(self) -> None:
        """Show backups view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(BackupManagerUI(id="backups"))
        self.current_state = AppState.BACKUPS
        self._update_nav_highlight("nav_backups")

    def show_logs(self) -> None:
        """Show logs view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(LogViewer(id="logs"))
        self.current_state = AppState.LOGS
        self._update_nav_highlight("nav_logs")

    def show_config(self) -> None:
        """Show config view."""
        main_content = self.query_one("#main_content", Container)
        main_content.remove_children()
        main_content.mount(Static("⚙️  Configuration\n\nConfiguration management coming soon..."))
        self.current_state = AppState.CONFIG
        self._update_nav_highlight("nav_config")

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

    def show_instance_actions(self, instance: InstanceInfo) -> None:
        """Show action dialog for selected instance."""
        # Create a simple action dialog
        actions = [
            ("▶️  Start", "start"),
            ("⏸️  Stop", "stop"),
            ("🔄 Restart", "restart"),
            ("📜 View Logs", "logs"),
            ("🗑️  Remove", "remove"),
            ("ℹ️  Info", "info"),
        ]

        # For now, just notify with the available actions
        # In a full implementation, we'd show a proper dialog
        self.notify(f"Selected: {instance.name} ({instance.status})", severity="information")

    def refresh_instances(self) -> None:
        """Refresh instance list if visible."""
        try:
            instances = self.query_one(InstanceTable)
            if instances:
                instances.refresh_instances()
        except:
            pass

    def action_refresh(self) -> None:
        """Refresh current view."""
        if self.current_state == AppState.DASHBOARD:
            try:
                dashboard = self.query_one(Dashboard)
                dashboard.update_stats()
            except:
                pass
        elif self.current_state == AppState.INSTANCES:
            self.refresh_instances()
        elif self.current_state == AppState.DATABASES:
            try:
                db_mgr = self.query_one(DatabaseManagerUI)
                db_mgr._load_instances()
            except:
                pass
        elif self.current_state == AppState.LOGS:
            try:
                log_viewer = self.query_one(LogViewer)
                log_viewer._load_instances()
            except:
                pass

    def action_new_instance(self) -> None:
        """Show create instance dialog."""
        self.push_screen(CreateInstanceScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        button_id = event.button.id

        # Navigation
        if button_id == "nav_dashboard":
            self.show_dashboard()
        elif button_id == "nav_instances":
            self.show_instances()
        elif button_id == "nav_databases":
            self.show_databases()
        elif button_id == "nav_modules":
            self.show_modules()
        elif button_id == "nav_backups":
            self.show_backups()
        elif button_id == "nav_logs":
            self.show_logs()
        elif button_id == "nav_config":
            self.show_config()

        # Dashboard actions
        elif button_id == "btn_new_instance":
            self.action_new_instance()
        elif button_id == "btn_refresh_all":
            self.action_refresh()

        # Instance table actions
        elif button_id == "btn_create_instance":
            self.action_new_instance()
        elif button_id == "btn_refresh_instances":
            self.refresh_instances()


def launch_tui():
    """Launch the TUI application."""
    app = OdooManagerTUI()
    app.run()
