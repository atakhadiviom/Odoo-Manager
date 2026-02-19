"""
Docker deployment strategy using docker-compose.
"""

import subprocess
import time
from pathlib import Path
from typing import Any

import jinja2
from docker import from_env
from docker.errors import DockerException as DockerError
from docker.models.containers import Container

from odoo_manager.config import InstanceConfig
from odoo_manager.constants import (
    DEFAULT_POSTGRES_DB,
    DEFAULT_POSTGRES_PASSWORD,
    DEFAULT_POSTGRES_PORT,
    DEFAULT_POSTGRES_USER,
    STATE_ERROR,
    STATE_RUNNING,
    STATE_STOPPED,
    STATE_UNKNOWN,
)
from odoo_manager.deployers.base import BaseDeployer
from odoo_manager.exceptions import DockerError as OdooDockerError


def get_docker_compose_command() -> list[str]:
    """Get the appropriate docker-compose command."""
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return ["docker", "compose"]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        result = subprocess.run(
            ["docker-compose", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return ["docker-compose"]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Default to docker compose (plugin version)
    return ["docker", "compose"]


class DockerDeployer(BaseDeployer):
    """Docker deployment strategy using docker-compose."""

    COMPOSE_FILE = "docker-compose.yml"

    def __init__(self, instance: InstanceConfig, data_dir: Path):
        super().__init__(instance, data_dir)
        self.compose_cmd = get_docker_compose_command()
        self.compose_file = self.data_dir / self.COMPOSE_FILE
        self._docker_client = None  # Lazy initialization

        self._container_names = {
            "odoo": f"odoo-{self.instance.name}",
            "postgres": f"odoo-{self.instance.name}-db",
        }

    @property
    def docker_client(self):
        """Lazy load Docker client."""
        if self._docker_client is None:
            try:
                self._docker_client = from_env()
            except DockerError as e:
                raise OdooDockerError(f"Cannot connect to Docker daemon: {e}")
        return self._docker_client

    def create(self) -> None:
        """Create the instance deployment."""
        self.ensure_data_dir()
        self._generate_compose_file()

    def start(self) -> None:
        """Start the instance using docker-compose."""
        if not self.compose_file.exists():
            self.create()

        cmd = self.compose_cmd + ["-f", str(self.compose_file), "up", "-d"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise OdooDockerError(f"Failed to start instance: {result.stderr}")

    def stop(self) -> None:
        """Stop the instance using docker-compose."""
        if not self.compose_file.exists():
            return

        cmd = self.compose_cmd + ["-f", str(self.compose_file), "stop"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise OdooDockerError(f"Failed to stop instance: {result.stderr}")

    def restart(self) -> None:
        """Restart the instance using docker-compose."""
        if not self.compose_file.exists():
            return

        cmd = self.compose_cmd + ["-f", str(self.compose_file), "restart"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise OdooDockerError(f"Failed to restart instance: {result.stderr}")

    def status(self) -> str:
        """Get the current status of the instance."""
        try:
            container = self._get_container("odoo")
            if container is None:
                return STATE_STOPPED

            status = container.status.lower()
            if "running" in status:
                return STATE_RUNNING
            elif "exited" in status:
                return STATE_STOPPED
            else:
                return STATE_UNKNOWN
        except Exception:
            return STATE_ERROR

    def is_running(self) -> bool:
        """Check if the instance is running."""
        return self.status() == STATE_RUNNING

    def remove(self) -> None:
        """Remove the instance deployment."""
        if not self.compose_file.exists():
            return

        # Stop and remove containers
        cmd = self.compose_cmd + ["-f", str(self.compose_file), "down", "-v"]
        subprocess.run(cmd, capture_output=True, text=True)

        # Optionally remove the compose file
        if self.compose_file.exists():
            self.compose_file.unlink()

    def exec_command(self, command: list[str], capture: bool = False) -> str | int:
        """Execute a command in the Odoo container."""
        container_name = self._container_names["odoo"]
        cmd = ["docker", "exec"]

        if not capture:
            cmd += ["-it"]

        cmd += [container_name] + command

        if capture:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout if result.returncode == 0 else result.stderr
        else:
            return subprocess.run(cmd).returncode

    def get_logs(self, follow: bool = False, tail: int = 100) -> str:
        """Get logs from the instance."""
        try:
            container = self._get_container("odoo")
            if container is None:
                return "Container not found"

            logs = container.logs(tail=tail, follow=follow)
            if follow:
                # For follow mode, we need to stream the logs
                for line in logs:
                    print(line.decode("utf-8", errors="ignore").rstrip())
                return ""
            else:
                return logs.decode("utf-8", errors="ignore")
        except Exception as e:
            return f"Error getting logs: {e}"

    def _get_container(self, service: str) -> Container | None:
        """Get a Docker container by service name."""
        try:
            client = self.docker_client
            return client.containers.get(self._container_names[service])
        except (DockerError, OdooDockerError):
            # Docker not available or not running
            return None
        except Exception:
            return None

    def _generate_compose_file(self) -> None:
        """Generate the docker-compose.yml file."""
        from pathlib import Path
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(Path(__file__).parent.parent / "templates"))

        try:
            template = env.get_template("docker-compose.yml.j2")
        except jinja2.TemplateNotFound:
            # Fallback to inline template
            template_content = self._get_default_compose_template()
            template = jinja2.Template(template_content)

        context = self._get_template_context()
        content = template.render(**context)

        with open(self.compose_file, "w") as f:
            f.write(content)

    def _get_template_context(self) -> dict[str, Any]:
        """Get the context for template rendering."""
        return {
            "instance": self.instance,
            "odoo_image": self.instance.get_odoo_image(),
            "postgres_image": self.instance.postgres_image,
            "container_names": self._container_names,
            "data_dir": self.data_dir,
            "postgres_user": self.instance.db_user or DEFAULT_POSTGRES_USER,
            "postgres_password": self.instance.db_password or DEFAULT_POSTGRES_PASSWORD,
            "postgres_db": DEFAULT_POSTGRES_DB,
            "db_host": "postgres",
            "db_port": DEFAULT_POSTGRES_PORT,
        }

    def _get_default_compose_template(self) -> str:
        """Get the default docker-compose template."""
        return '''version: '3.8'

services:
  odoo:
    image: {{ odoo_image }}
    container_name: {{ container_names.odoo }}
    depends_on:
      - postgres
    ports:
      - "{{ instance.port }}:8069"
    environment:
      HOST: {{ db_host }}
      PORT: {{ db_port }}
      USER: {{ postgres_user }}
      PASSWORD: {{ postgres_password }}
    volumes:
      - odoo-data:/var/lib/odoo
      - ./addons:/mnt/extra-addons
    restart: unless-stopped
    command: --
      --db-host={{ db_host }}
      --db-port={{ db_port }}
      --db-user={{ postgres_user }}
      --db-password={{ postgres_password }}
      --db-filter={{ instance.db_filter }}
      --workers={{ instance.workers }}
      --max-cron-threads={{ instance.max_cron_threads }}
      --db-maxconn={{ instance.db_maxconn }}
      --admin-password={{ instance.admin_password }}
      {% if instance.addons_path %}--addons-path={{ instance.addons_path }}{% endif %}
      --without-demo={{ instance.without_demo | lower }}

  postgres:
    image: {{ postgres_image }}
    container_name: {{ container_names.postgres }}
    environment:
      POSTGRES_USER: {{ postgres_user }}
      POSTGRES_PASSWORD: {{ postgres_password }}
      POSTGRES_DB: {{ postgres_db }}
    volumes:
      - db-data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  odoo-data:
  db-data:
'''

    def get_container_info(self) -> dict[str, Any]:
        """Get information about the instance containers."""
        info = {
            "odoo": None,
            "postgres": None,
        }

        for service in ["odoo", "postgres"]:
            container = self._get_container(service)
            if container:
                info[service] = {
                    "id": container.id[:12],
                    "name": container.name,
                    "status": container.status,
                    "image": container.image.tags[0] if container.image.tags else str(container.image.id),
                }

        return info
