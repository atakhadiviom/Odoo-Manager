"""
Database operations for Odoo instances.
"""

from pathlib import Path
from subprocess import run
from typing import Any

from odoo_manager.config import InstanceConfig
from odoo_manager.constants import DEPLOYMENT_DOCKER
from odoo_manager.deployers.docker import DockerDeployer
from odoo_manager.exceptions import DatabaseError, DatabaseNotFoundError


class DatabaseManager:
    """Manages databases for an Odoo instance."""

    def __init__(self, instance: InstanceConfig, data_dir: Path):
        self.instance = instance
        self.data_dir = data_dir / instance.name
        self.deployer = DockerDeployer(instance, data_dir)

    def list_databases(self) -> list[dict[str, Any]]:
        """List all databases in the instance."""
        if self.instance.deployment_type == DEPLOYMENT_DOCKER:
            return self._list_databases_docker()
        else:
            raise NotImplementedError("Database listing not implemented for source deployment")

    def _list_databases_docker(self) -> list[dict[str, Any]]:
        """List databases using Docker exec."""
        container_name = self.deployer._container_names["postgres"]
        cmd = [
            "docker", "exec", "-t", container_name,
            "psql", "-U", self.instance.db_user or "odoo",
            "-d", "postgres", "-c",
            "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname"
        ]

        result = run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise DatabaseError(f"Failed to list databases: {result.stderr}")

        databases = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            # Skip header and separator lines
            if line and not line.startswith("datname") and not line.startswith("---"):
                databases.append({
                    "name": line,
                    "size": "N/A",
                })

        return databases

    def database_exists(self, name: str) -> bool:
        """Check if a database exists."""
        databases = self.list_databases()
        return any(db["name"] == name for db in databases)

    def create_database(self, name: str) -> None:
        """Create a new database."""
        if self.database_exists(name):
            raise DatabaseError(f"Database '{name}' already exists")

        if self.instance.deployment_type == DEPLOYMENT_DOCKER:
            self._create_database_docker(name)
        else:
            raise NotImplementedError("Database creation not implemented for source deployment")

    def _create_database_docker(self, name: str) -> None:
        """Create a database using Docker exec."""
        container_name = self.deployer._container_names["postgres"]
        cmd = [
            "docker", "exec", "-t", container_name,
            "psql", "-U", self.instance.db_user or "odoo",
            "-d", "postgres", "-c", f"CREATE DATABASE {name}"
        ]

        result = run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise DatabaseError(f"Failed to create database: {result.stderr}")

    def drop_database(self, name: str) -> None:
        """Drop a database."""
        if not self.database_exists(name):
            raise DatabaseNotFoundError(name)

        if self.instance.deployment_type == DEPLOYMENT_DOCKER:
            self._drop_database_docker(name)
        else:
            raise NotImplementedError("Database drop not implemented for source deployment")

    def _drop_database_docker(self, name: str) -> None:
        """Drop a database using Docker exec."""
        container_name = self.deployer._container_names["postgres"]

        # Terminate connections first
        terminate_cmd = [
            "docker", "exec", "-t", container_name,
            "psql", "-U", self.instance.db_user or "odoo",
            "-d", "postgres", "-c",
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{name}'"
        ]
        run(terminate_cmd, capture_output=True)

        # Drop the database
        cmd = [
            "docker", "exec", "-t", container_name,
            "psql", "-U", self.instance.db_user or "odoo",
            "-d", "postgres", "-c", f"DROP DATABASE {name}"
        ]

        result = run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise DatabaseError(f"Failed to drop database: {result.stderr}")

    def duplicate_database(self, source: str, target: str) -> None:
        """Duplicate a database."""
        if not self.database_exists(source):
            raise DatabaseNotFoundError(source)

        if self.database_exists(target):
            raise DatabaseError(f"Target database '{target}' already exists")

        if self.instance.deployment_type == DEPLOYMENT_DOCKER:
            self._duplicate_database_docker(source, target)
        else:
            raise NotImplementedError("Database duplication not implemented for source deployment")

    def _duplicate_database_docker(self, source: str, target: str) -> None:
        """Duplicate a database using Docker exec."""
        container_name = self.deployer._container_names["postgres"]
        cmd = [
            "docker", "exec", "-t", container_name,
            "psql", "-U", self.instance.db_user or "odoo",
            "-d", "postgres", "-c", f"CREATE DATABASE {target} TEMPLATE {source}"
        ]

        result = run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise DatabaseError(f"Failed to duplicate database: {result.stderr}")

    def backup_database(self, name: str, output_path: Path) -> None:
        """Backup a database to a file."""
        if not self.database_exists(name):
            raise DatabaseNotFoundError(name)

        if self.instance.deployment_type == DEPLOYMENT_DOCKER:
            self._backup_database_docker(name, output_path)
        else:
            raise NotImplementedError("Database backup not implemented for source deployment")

    def _backup_database_docker(self, name: str, output_path: Path) -> None:
        """Backup a database using Docker exec."""
        container_name = self.deployer._container_names["postgres"]

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use pg_dump inside the container and pipe to local file
        cmd = [
            "docker", "exec", "-t", container_name,
            "pg_dump", "-U", self.instance.db_user or "odoo",
            "-F", "c", "-f", f"/tmp/{name}.dump", name
        ]

        result = run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise DatabaseError(f"Failed to backup database: {result.stderr}")

        # Copy the dump file from the container
        copy_cmd = [
            "docker", "cp",
            f"{container_name}:/tmp/{name}.dump",
            str(output_path)
        ]

        result = run(copy_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise DatabaseError(f"Failed to copy backup file: {result.stderr}")

        # Clean up the temporary file in the container
        cleanup_cmd = [
            "docker", "exec", "-t", container_name,
            "rm", "-f", f"/tmp/{name}.dump"
        ]
        run(cleanup_cmd, capture_output=True)

    def restore_database(self, backup_path: Path, name: str) -> None:
        """Restore a database from a backup file."""
        if self.database_exists(name):
            raise DatabaseError(f"Database '{name}' already exists")

        if self.instance.deployment_type == DEPLOYMENT_DOCKER:
            self._restore_database_docker(backup_path, name)
        else:
            raise NotImplementedError("Database restore not implemented for source deployment")

    def _restore_database_docker(self, backup_path: Path, name: str) -> None:
        """Restore a database using Docker exec."""
        container_name = self.deployer._container_names["postgres"]

        # Copy the backup file to the container
        copy_cmd = [
            "docker", "cp",
            str(backup_path),
            f"{container_name}:/tmp/{name}.dump"
        ]

        result = run(copy_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise DatabaseError(f"Failed to copy backup file: {result.stderr}")

        # Create the database first
        create_cmd = [
            "docker", "exec", "-t", container_name,
            "psql", "-U", self.instance.db_user or "odoo",
            "-d", "postgres", "-c", f"CREATE DATABASE {name}"
        ]
        run(create_cmd, capture_output=True)

        # Restore the database
        restore_cmd = [
            "docker", "exec", "-t", container_name,
            "pg_restore", "-U", self.instance.db_user or "odoo",
            "-d", name, "-j", "4", f"/tmp/{name}.dump"
        ]

        result = run(restore_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            # Clean up the database if restore failed
            run([
                "docker", "exec", "-t", container_name,
                "psql", "-U", self.instance.db_user or "odoo",
                "-d", "postgres", "-c", f"DROP DATABASE {name}"
            ], capture_output=True)
            raise DatabaseError(f"Failed to restore database: {result.stderr}")

        # Clean up the temporary file
        cleanup_cmd = [
            "docker", "exec", "-t", container_name,
            "rm", "-f", f"/tmp/{name}.dump"
        ]
        run(cleanup_cmd, capture_output=True)
