"""
Simplified Odoo instance management.

Handles instance creation, start/stop/restart, status, and removal.
Uses Docker Compose for deployment.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from odoo_manager.config import InstanceConfig, InstancesFile
from odoo_manager.constants import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_POSTGRES_DB,
    DEFAULT_POSTGRES_IMAGE,
    DEFAULT_POSTGRES_PASSWORD,
    DEFAULT_POSTGRES_PORT,
    DEFAULT_POSTGRES_USER,
)


class Instance:
    """A single Odoo instance managed with Docker Compose."""

    # Environment tiers
    ENV_DEV = "dev"
    ENV_STAGING = "staging"
    ENV_PRODUCTION = "production"

    def __init__(self, config: InstanceConfig):
        self.config = config
        self.data_dir = Path.home() / "odoo-manager" / "data" / config.name
        self.compose_file = self.data_dir / "docker-compose.yml"
        self.addons_dir = self.data_dir / "addons"
        self.custom_dir = self.data_dir / "custom"

    @property
    def container_name(self) -> str:
        """Get the Odoo container name."""
        return f"odoo-{self.config.name}"

    @property
    def db_container_name(self) -> str:
        """Get the PostgreSQL container name."""
        return f"odoo-{self.config.name}-db"

    def _get_docker_cmd(self) -> list[str]:
        """Get docker command with sudo if needed."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return ["docker"]
        except Exception:
            pass
        return ["sudo", "docker"]

    def _ensure_data_dir(self) -> None:
        """Ensure data directory exists with proper permissions."""
        # Fix ownership if directory exists but not writable
        if self.data_dir.exists():
            if not os.access(self.data_dir, os.W_OK):
                user = os.environ.get("USER", os.environ.get("USERNAME", "ubuntu"))
                subprocess.run(
                    ["sudo", "chown", "-R", f"{user}:{user}", str(self.data_dir)],
                    check=False,
                    capture_output=True
                )
        else:
            # Create parent directories
            parent = self.data_dir.parent
            if not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)

            # Fix parent ownership if needed
            if not os.access(parent, os.W_OK):
                user = os.environ.get("USER", os.environ.get("USERNAME", "ubuntu"))
                subprocess.run(
                    ["sudo", "chown", "-R", f"{user}:{user}", str(parent)],
                    check=False,
                    capture_output=True
                )

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.addons_dir.mkdir(exist_ok=True)
        self.custom_dir.mkdir(exist_ok=True)

    def _generate_compose_file(self) -> None:
        """Generate docker-compose.yml file."""
        # Determine DB name based on environment
        db_name = self.config.db_name
        if self.config.environment == self.ENV_DEV:
            db_name = f"{self.config.name}_dev"
        elif self.config.environment == self.ENV_STAGING:
            db_name = f"{self.config.name}_staging"

        compose_content = f"""services:
  odoo:
    image: {self.config.get_odoo_image()}
    container_name: {self.container_name}
    depends_on:
      - postgres
    ports:
      - "{self.config.port}:8069"
    environment:
      # Odoo database configuration
      HOST: postgres
      PORT: 5432
      USER: {self.config.db_user}
      PASSWORD: {self.config.db_password}
    volumes:
      - odoo-data:/var/lib/odoo
      - ./addons:/mnt/extra-addons
      - ./custom:/mnt/extra-addons/custom
    restart: unless-stopped

  postgres:
    image: {self.config.postgres_image}
    container_name: {self.db_container_name}
    environment:
      POSTGRES_USER: {self.config.db_user}
      POSTGRES_PASSWORD: {self.config.db_password}
      POSTGRES_DB: {db_name}
    volumes:
      - db-data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  odoo-data:
  db-data:
"""

        with open(self.compose_file, "w") as f:
            f.write(compose_content)

    def create(self) -> None:
        """Create the instance deployment files."""
        self._ensure_data_dir()
        self._generate_compose_file()

    def start(self) -> None:
        """Start the instance."""
        if not self.compose_file.exists():
            self.create()

        docker_cmd = self._get_docker_cmd()
        cmd = docker_cmd + ["compose", "-f", str(self.compose_file), "up", "-d"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start instance: {result.stderr}")

    def stop(self) -> None:
        """Stop the instance."""
        if not self.compose_file.exists():
            return

        docker_cmd = self._get_docker_cmd()
        cmd = docker_cmd + ["compose", "-f", str(self.compose_file), "stop"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to stop instance: {result.stderr}")

    def restart(self) -> None:
        """Restart the instance."""
        if not self.compose_file.exists():
            return

        docker_cmd = self._get_docker_cmd()
        cmd = docker_cmd + ["compose", "-f", str(self.compose_file), "restart"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to restart instance: {result.stderr}")

    def status(self) -> str:
        """Get instance status: running, stopped, or error."""
        docker_cmd = self._get_docker_cmd()

        try:
            result = subprocess.run(
                docker_cmd + ["ps", "-a", "--filter", f"name={self.container_name}",
                             "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            status_output = result.stdout.strip()

            if not status_output:
                return "stopped"

            status_lower = status_output.lower()
            if "running" in status_lower or "up" in status_lower:
                return "running"
            elif "exited" in status_lower or "dead" in status_lower:
                return "stopped"
            else:
                return "unknown"
        except Exception:
            return "error"

    def is_running(self) -> bool:
        """Check if the instance is running."""
        return self.status() == "running"

    def remove(self) -> None:
        """Remove the instance deployment."""
        if not self.compose_file.exists():
            return

        docker_cmd = self._get_docker_cmd()
        cmd = docker_cmd + ["compose", "-f", str(self.compose_file), "down", "-v"]
        subprocess.run(cmd, capture_output=True, text=True)

    def get_logs(self, tail: int = 100, follow: bool = False) -> str:
        """Get logs from the Odoo container."""
        docker_cmd = self._get_docker_cmd()

        if follow:
            # For follow mode, we need to stream
            cmd = docker_cmd + ["logs", "-f", "--tail", str(tail), self.container_name]
            subprocess.run(cmd)
            return ""
        else:
            cmd = docker_cmd + ["logs", "--tail", str(tail), self.container_name]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout

    def exec_command(self, command: list[str]) -> str:
        """Execute a command in the Odoo container."""
        docker_cmd = self._get_docker_cmd()
        cmd = docker_cmd + ["exec", self.container_name] + command
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr


class InstanceManager:
    """Manage multiple Odoo instances."""

    def __init__(self):
        self.instances_file = InstancesFile()
        self._instances_config: Optional[InstancesFile] = None

    def _load_config(self) -> InstancesFile:
        """Load instances configuration."""
        if self._instances_config is None:
            self._instances_config = self.instances_file.load()
        return self._instances_config

    def _save_config(self) -> None:
        """Save instances configuration."""
        if self._instances_config:
            self.instances_file.save(self._instances_config)

    def create_instance(
        self,
        name: str,
        version: str = "19.0",
        edition: str = "community",
        port: int = 8069,
        workers: int = 4,
        environment: str = Instance.ENV_DEV,
        git_repo: Optional[str] = None,
    ) -> Instance:
        """Create a new Odoo instance.

        Args:
            name: Instance name
            version: Odoo version (17.0, 18.0, 19.0)
            edition: community or enterprise
            port: Port number for Odoo
            workers: Number of worker processes
            environment: dev, staging, or production
            git_repo: Optional Git repository URL for custom modules

        Returns:
            The created Instance object
        """
        config = InstanceConfig(
            name=name,
            version=version,
            edition=edition,
            port=port,
            workers=workers,
            db_name=name,
            deployment_type="docker",
            environment=environment,
            git_repo=git_repo,
        )

        instances_config = self._load_config()
        instances_config.add_instance(config)
        self._save_config()

        instance = Instance(config)
        instance.create()

        return instance

    def get_instance(self, name: str) -> Optional[Instance]:
        """Get an instance by name."""
        instances_config = self._load_config()
        config = instances_config.get_instance(name)
        if config:
            return Instance(config)
        return None

    def list_instances(self) -> list[Instance]:
        """List all instances."""
        instances_config = self._load_config()
        return [Instance(cfg) for cfg in instances_config.list_instances()]

    def remove_instance(self, name: str) -> None:
        """Remove an instance."""
        instances_config = self._load_config()

        # First stop and remove containers
        instance = self.get_instance(name)
        if instance:
            instance.remove()

        # Then remove from config
        instances_config.remove_instance(name)
        self._save_config()
