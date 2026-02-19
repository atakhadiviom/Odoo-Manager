"""
Database management for Odoo instances.

Handles creating, duplicating, backing up, and restoring databases.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from odoo_manager.instance import Instance


class DatabaseManager:
    """Manage PostgreSQL databases for an Odoo instance."""

    def __init__(self, instance: Instance):
        self.instance = instance
        self.backup_dir = Path.home() / "odoo-manager" / "backups" / instance.config.name
        self.backup_dir.mkdir(parents=True, exist_ok=True)

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

    def list_databases(self) -> list[str]:
        """List all databases in the instance's PostgreSQL container."""
        docker_cmd = self._get_docker_cmd()

        cmd = docker_cmd + ["exec", self.instance.db_container_name,
                           "psql", "-U", self.instance.config.db_user,
                           "-c", "SELECT datname FROM pg_database WHERE datistemplate = false"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return []

        databases = []
        for line in result.stdout.strip().split("\n")[2:]:  # Skip header
            line = line.strip()
            if line and line != self.instance.config.db_user:
                databases.append(line)

        return databases

    def create(self, db_name: str) -> None:
        """Create a new database.

        Args:
            db_name: Name for the new database
        """
        docker_cmd = self._get_docker_cmd()

        cmd = docker_cmd + ["exec", self.instance.db_container_name,
                           "createdb", "-U", self.instance.config.db_user, db_name]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create database: {result.stderr}")

    def drop(self, db_name: str) -> None:
        """Drop a database.

        Args:
            db_name: Name of the database to drop
        """
        docker_cmd = self._get_docker_cmd()

        cmd = docker_cmd + ["exec", self.instance.db_container_name,
                           "dropdb", "-U", self.instance.config.db_user, db_name]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to drop database: {result.stderr}")

    def duplicate(self, source_db: str, target_db: str) -> None:
        """Duplicate a database.

        Args:
            source_db: Name of the source database
            target_db: Name for the new database
        """
        docker_cmd = self._get_docker_cmd()

        # Create a backup and restore it
        backup_file = f"/tmp/{source_db}_temp.dump"

        # Dump the source database
        dump_cmd = docker_cmd + ["exec", self.instance.db_container_name,
                                "pg_dump", "-U", self.instance.config.db_user,
                                "-F", "c", source_db, "-f", backup_file]
        subprocess.run(dump_cmd, capture_output=True, text=True)

        # Create the new database
        self.create(target_db)

        # Restore to the new database
        restore_cmd = docker_cmd + ["exec", self.instance.db_container_name,
                                   "pg_restore", "-U", self.instance.config.db_user,
                                   "-d", target_db, backup_file]
        subprocess.run(restore_cmd, capture_output=True, text=True)

        # Clean up temp file
        cleanup_cmd = docker_cmd + ["exec", self.instance.db_container_name, "rm", backup_file]
        subprocess.run(cleanup_cmd, capture_output=True, text=True)

    def backup(self, db_name: Optional[str] = None) -> Path:
        """Backup a database to a file.

        Args:
            db_name: Database name to backup, defaults to instance database

        Returns:
            Path to the backup file
        """
        if db_name is None:
            db_name = self.instance.config.db_name

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"{db_name}_{timestamp}.dump"

        docker_cmd = self._get_docker_cmd()

        # Dump to container's tmp, then copy out
        container_backup = f"/tmp/{db_name}_{timestamp}.dump"

        dump_cmd = docker_cmd + ["exec", self.instance.db_container_name,
                                "pg_dump", "-U", self.instance.config.db_user,
                                "-F", "c", "-f", container_backup, db_name]

        result = subprocess.run(dump_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to backup database: {result.stderr}")

        # Copy backup file from container
        copy_cmd = docker_cmd + ["cp", f"{self.instance.db_container_name}:{container_backup}",
                                str(backup_file)]

        subprocess.run(copy_cmd, capture_output=True, text=True)

        # Clean up container temp file
        cleanup_cmd = docker_cmd + ["exec", self.instance.db_container_name, "rm", container_backup]
        subprocess.run(cleanup_cmd, capture_output=True, text=True)

        return backup_file

    def restore(self, backup_file: Path, target_db: Optional[str] = None) -> None:
        """Restore a database from a backup file.

        Args:
            backup_file: Path to the backup file
            target_db: Target database name, defaults to instance database
        """
        if target_db is None:
            target_db = self.instance.config.db_name

        docker_cmd = self._get_docker_cmd()

        # Copy backup file into container
        container_backup = f"/tmp/{backup_file.name}"
        copy_cmd = docker_cmd + ["cp", str(backup_file),
                                f"{self.instance.db_container_name}:{container_backup}"]
        subprocess.run(copy_cmd, capture_output=True, text=True)

        # Create database if it doesn't exist
        if target_db not in self.list_databases():
            self.create(target_db)

        # Restore the backup
        restore_cmd = docker_cmd + ["exec", self.instance.db_container_name,
                                   "pg_restore", "-U", self.instance.config.db_user,
                                   "-d", target_db, container_backup]

        result = subprocess.run(restore_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to restore database: {result.stderr}")

        # Clean up
        cleanup_cmd = docker_cmd + ["exec", self.instance.db_container_name, "rm", container_backup]
        subprocess.run(cleanup_cmd, capture_output=True, text=True)

    def list_backups(self) -> list[dict]:
        """List all backup files for this instance.

        Returns:
            List of backup info dictionaries
        """
        backups = []
        for backup_file in self.backup_dir.glob("*.dump"):
            stat = backup_file.stat()
            backups.append({
                "name": backup_file.name,
                "path": str(backup_file),
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime),
            })
        return sorted(backups, key=lambda x: x["created"], reverse=True)
