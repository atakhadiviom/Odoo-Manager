"""
Source deployment strategy using systemd and virtual environment.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import jinja2

from odoo_manager.config import InstanceConfig
from odoo_manager.constants import (
    DEFAULT_POSTGRES_DB,
    DEFAULT_POSTGRES_IMAGE,
    DEFAULT_POSTGRES_PASSWORD,
    DEFAULT_POSTGRES_PORT,
    DEFAULT_POSTGRES_USER,
    STATE_ERROR,
    STATE_RUNNING,
    STATE_STOPPED,
    STATE_UNKNOWN,
)
from odoo_manager.deployers.base import BaseDeployer
from odoo_manager.exceptions import DeploymentError as OdooDeploymentError


class SourceDeployer(BaseDeployer):
    """Source deployment strategy using systemd and virtual environment."""

    def __init__(self, instance: InstanceConfig, data_dir: Path):
        super().__init__(instance, data_dir)
        self.venv_dir = self.data_dir / "venv"
        self.source_dir = self.data_dir / "src"
        self.etc_dir = self.data_dir / "etc"
        self.log_dir = self.data_dir / "log"
        self.service_file = Path("/etc/systemd/system") / f"odoo-{self.instance.name}.service"
        self.config_file = self.etc_dir / "odoo.conf"

    def create(self) -> None:
        """Create the source deployment."""
        self.ensure_data_dir()
        self.venv_dir.mkdir(parents=True, exist_ok=True)
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.etc_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create virtual environment
        self._create_venv()

        # Install Odoo from source
        self._install_odoo()

        # Generate odoo.conf
        self._generate_config()

        # Generate systemd service
        self._generate_service()

    def start(self) -> None:
        """Start the instance using systemd."""
        if not self.service_file.exists():
            self.create()

        try:
            subprocess.run(
                ["systemctl", "daemon-reload"], check=True, capture_output=True
            )
            subprocess.run(
                ["systemctl", "enable", f"odoo-{self.instance.name}"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["systemctl", "start", f"odoo-{self.instance.name}"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise OdooDeploymentError(f"Failed to start instance: {e.stderr.decode()}")

    def stop(self) -> None:
        """Stop the instance using systemd."""
        if not self.service_file.exists():
            return

        try:
            subprocess.run(
                ["systemctl", "stop", f"odoo-{self.instance.name}"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise OdooDeploymentError(f"Failed to stop instance: {e.stderr.decode()}")

    def restart(self) -> None:
        """Restart the instance using systemd."""
        if not self.service_file.exists():
            return

        try:
            subprocess.run(
                ["systemctl", "restart", f"odoo-{self.instance.name}"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise OdooDeploymentError(f"Failed to restart instance: {e.stderr.decode()}")

    def status(self) -> str:
        """Get the current status of the instance."""
        if not self.service_file.exists():
            return STATE_STOPPED

        try:
            result = subprocess.run(
                ["systemctl", "is-active", f"odoo-{self.instance.name}"],
                capture_output=True,
                text=True,
            )
            active = result.stdout.strip()

            if active == "active":
                return STATE_RUNNING
            elif active in ("inactive", "dead"):
                return STATE_STOPPED
            elif active == "failed":
                return STATE_ERROR
            else:
                return STATE_UNKNOWN

        except Exception:
            return STATE_ERROR

    def is_running(self) -> bool:
        """Check if the instance is running."""
        return self.status() == STATE_RUNNING

    def remove(self) -> None:
        """Remove the instance deployment."""
        # Stop and disable service
        if self.service_file.exists():
            subprocess.run(
                ["systemctl", "stop", f"odoo-{self.instance.name}"],
                capture_output=True,
            )
            subprocess.run(
                ["systemctl", "disable", f"odoo-{self.instance.name}"],
                capture_output=True,
            )
            self.service_file.unlink()
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True)

        # Remove data directory
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)

    def exec_command(self, command: list[str], capture: bool = False) -> str | int:
        """Execute a command in the Odoo context."""
        python_bin = self.venv_dir / "bin" / "python"
        odoo_bin = self.source_dir / "odoo-bin"

        if not odoo_bin.exists():
            odoo_bin = self.source_dir / "odoo" / "bin" / "odoo"

        cmd = [str(python_bin), str(odoo_bin)] + command

        # Set environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.source_dir)

        if capture:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=self.source_dir,
            )
            return result.stdout if result.returncode == 0 else result.stderr
        else:
            return subprocess.run(cmd, env=env, cwd=self.source_dir).returncode

    def get_logs(self, follow: bool = False, tail: int = 100) -> str:
        """Get logs from the instance."""
        log_file = self.log_dir / "odoo.log"

        if follow:
            # Use journalctl for systemd service
            cmd = ["journalctl", "-u", f"odoo-{self.instance.name}", "-f"]
            if tail > 0:
                cmd.extend(["-n", str(tail)])
            subprocess.run(cmd)
            return ""
        else:
            # Try journalctl first
            try:
                result = subprocess.run(
                    ["journalctl", "-u", f"odoo-{self.instance.name}", "-n", str(tail), "--no-pager"],
                    capture_output=True,
                    text=True,
                )
                return result.stdout
            except Exception:
                # Fallback to log file
                if log_file.exists():
                    result = subprocess.run(
                        ["tail", "-n", str(tail), str(log_file)],
                        capture_output=True,
                        text=True,
                    )
                    return result.stdout
                return "Log file not found"

    def _create_venv(self) -> None:
        """Create Python virtual environment."""
        if self.venv_dir.exists() and (self.venv_dir / "bin" / "python").exists():
            return  # Already exists

        try:
            subprocess.run(
                ["python3", "-m", "venv", str(self.venv_dir)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise OdooDeploymentError(f"Failed to create venv: {e.stderr.decode()}")

    def _install_odoo(self) -> None:
        """Install Odoo from source or pip."""
        pip_bin = self.venv_dir / "bin" / "pip"

        # Install base requirements
        requirements = [
            "psycopg2-binary",
            "python-dateutil",
            "pytz",
            "Babel",
            "pyopenssl",
            "requests",
            "werkzeug",
            "passlib",
            "decorator",
        ]

        try:
            subprocess.run(
                [str(pip_bin), "install"] + requirements,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise OdooDeploymentError(f"Failed to install requirements: {e.stderr.decode()}")

        # If git_repo is specified, clone and install
        if self.instance.git_repo:
            self._clone_odoo_source()
        else:
            # Install from pip
            version = self.instance.version.replace(".", "")  # e.g., "17.0" -> "170"
            try:
                subprocess.run(
                    [str(pip_bin), "install", f"odoo{version}"],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                raise OdooDeploymentError(f"Failed to install Odoo: {e.stderr.decode()}")

    def _clone_odoo_source(self) -> None:
        """Clone Odoo source from git repository."""
        from odoo_manager.core.git import GitManager

        git_mgr = GitManager()

        # Clone if not already exists
        if not (self.source_dir / ".git").exists():
            git_mgr.clone(
                url=self.instance.git_repo,
                name=f"odoo-{self.instance.name}",
                branch=self.instance.git_branch,
            )

    def _generate_config(self) -> None:
        """Generate odoo.conf file."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(Path(__file__).parent.parent / "templates")
        )

        try:
            template = env.get_template("odoo.conf.j2")
        except jinja2.TemplateNotFound:
            template_content = self._get_default_config_template()
            template = jinja2.Template(template_content)

        context = {
            "db_host": self.instance.db_host,
            "db_port": self.instance.db_port,
            "db_user": self.instance.db_user,
            "db_password": self.instance.db_password,
            "db_filter": self.instance.db_filter,
            "http_port": self.instance.port,
            "longpolling_port": self.instance.port + 3,  # Default for gevent
            "workers": self.instance.workers,
            "max_cron_threads": self.instance.max_cron_threads,
            "db_maxconn": self.instance.db_maxconn,
            "addons_path": self._get_addons_path(),
            "data_dir": str(self.data_dir / "data"),
            "admin_password": self.instance.admin_password,
            "list_db": True,
            "proxy_mode": self.instance.ssl_enabled,
            "log_level": "info",
            "log_handler": ":INFO",
            "log_db": False,
            "without_demo": self.instance.without_demo,
        }

        content = template.render(**context)

        with open(self.config_file, "w") as f:
            f.write(content)

    def _generate_service(self) -> None:
        """Generate systemd service file."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(Path(__file__).parent.parent / "templates")
        )

        try:
            template = env.get_template("systemd.service.j2")
        except jinja2.TemplateNotFound:
            template_content = self._get_default_service_template()
            template = jinja2.Template(template_content)

        context = {
            "instance": self.instance,
            "odoo_bin": self._get_odoo_bin(),
            "config_file": self.config_file,
            "log_dir": self.log_dir,
            "venv_dir": self.venv_dir,
            "source_dir": self.source_dir,
            "user": os.getenv("USER", "odoo"),
        }

        content = template.render(**context)

        # Write service file
        self.service_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.service_file, "w") as f:
            f.write(content)

    def _get_addons_path(self) -> str:
        """Get addons path for Odoo."""
        addons = [str(self.source_dir / "addons")]

        # Add enterprise if applicable
        if self.instance.edition == "enterprise":
            enterprise_addons = self.source_dir / "enterprise" / "addons"
            if enterprise_addons.exists():
                addons.append(str(enterprise_addons))

        # Add extra addons if specified
        if self.instance.addons_path:
            addons.append(self.instance.addons_path)

        return ",".join(addons)

    def _get_odoo_bin(self) -> Path:
        """Get path to Odoo binary."""
        possible_paths = [
            self.source_dir / "odoo-bin",
            self.source_dir / "odoo" / "bin" / "odoo",
            self.venv_dir / "bin" / "odoo",
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # Default to odoo-bin (will be created/installed)
        return self.source_dir / "odoo-bin"

    def _get_default_config_template(self) -> str:
        """Get default odoo.conf template."""
        return """[options]
; Database settings
db_host = {{ db_host }}
db_port = {{ db_port }}
db_user = {{ db_user }}
db_password = {{ db_password }}
dbfilter = {{ db_filter }}

; Server settings
http_port = {{ http_port }}
longpolling_port = {{ longpolling_port }}
workers = {{ workers }}
max_cron_threads = {{ max_cron_threads }}
db_maxconn = {{ db_maxconn }}

; Paths
addons_path = {{ addons_path }}
data_dir = {{ data_dir }}

; Security
admin_passwd = {{ admin_password }}
list_db = {{ list_db }}
proxy_mode = {{ proxy_mode }}

; Logging
log_level = {{ log_level }}
log_handler = {{ log_handler }}
log_db = {{ log_db }}

; Demo
without_demo = {{ without_demo }}
"""

    def _get_default_service_template(self) -> str:
        """Get default systemd service template."""
        return """[Unit]
Description=Odoo Instance {{ instance.name }}
After=network.target postgresql.service

[Service]
Type=simple
User={{ user }}
Group={{ user }}

WorkingDirectory={{ source_dir }}
Environment="PYTHONPATH={{ source_dir }}"

ExecStart={{ venv_dir }}/bin/python {{ odoo_bin }} -c {{ config_file }}

StandardOutput=append:{{ log_dir }}/odoo.log
StandardError=append:{{ log_dir }}/odoo.log

# Restart settings
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""

    def get_service_info(self) -> dict[str, Any]:
        """Get information about the systemd service."""
        info = {"running": self.is_running(), "status": self.status()}

        try:
            result = subprocess.run(
                ["systemctl", "show", f"odoo-{self.instance.name}"],
                capture_output=True,
                text=True,
            )

            for line in result.stdout.split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    info[key] = value

        except Exception:
            pass

        return info
