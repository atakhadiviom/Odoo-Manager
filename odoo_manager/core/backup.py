"""
Backup operations for Odoo instances.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from odoo_manager.config import Config
from odoo_manager.core.database import DatabaseManager
from odoo_manager.core.instance import Instance, InstanceManager
from odoo_manager.exceptions import BackupError


class BackupManager:
    """Manages backups for Odoo instances."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.backup_dir = Path(self.config.settings.backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(
        self,
        instance_name: str,
        database: str | None = None,
        name: str | None = None,
    ) -> Path:
        """Create a backup of an instance database."""
        instance_manager = InstanceManager()
        instance = instance_manager.get_instance(instance_name)

        if not instance.is_running():
            raise BackupError(f"Instance '{instance_name}' is not running")

        db_name = database or instance.config.db_name
        db_manager = DatabaseManager(instance.config, instance.data_dir)

        # Generate backup name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"{instance_name}_{db_name}_{timestamp}.dump"
        backup_path = self.backup_dir / backup_name

        # Create the backup
        db_manager.backup_database(db_name, backup_path)

        # Record metadata
        self._record_backup(instance_name, db_name, backup_path)

        return backup_path

    def restore_backup(
        self,
        backup_file: Path,
        instance_name: str,
        target_database: str | None = None,
    ) -> None:
        """Restore a backup to an instance."""
        if not backup_file.exists():
            raise BackupError(f"Backup file '{backup_file}' not found")

        instance_manager = InstanceManager()
        instance = instance_manager.get_instance(instance_name)

        db_name = target_database or instance.config.db_name
        db_manager = DatabaseManager(instance.config, instance.data_dir)

        db_manager.restore_database(backup_file, db_name)

    def list_backups(self, instance_name: str | None = None) -> list[dict[str, Any]]:
        """List all backups, optionally filtered by instance."""
        backups = []

        for backup_file in self.backup_dir.glob("*.dump"):
            try:
                info = self._parse_backup_filename(backup_file)
                if instance_name is None or info.get("instance") == instance_name:
                    info["path"] = backup_file
                    info["size"] = backup_file.stat().st_size
                    backups.append(info)
            except Exception:
                # Skip files that don't match expected format
                continue

        # Sort by date (newest first)
        backups.sort(key=lambda x: x.get("date", ""), reverse=True)

        return backups

    def delete_backup(self, backup_file: Path) -> None:
        """Delete a backup file."""
        if not backup_file.exists():
            raise BackupError(f"Backup file '{backup_file}' not found")

        backup_file.unlink()

    def cleanup_old_backups(
        self,
        instance_name: str,
        retention_days: int | None = None,
    ) -> list[Path]:
        """Remove old backups based on retention policy."""
        retention = retention_days or self.config.settings.backup_retention_days
        cutoff_date = datetime.now().timestamp() - (retention * 86400)

        removed = []
        for backup in self.list_backups(instance_name):
            backup_time = datetime.strptime(
                backup.get("date", ""), "%Y%m%d_%H%M%S"
            ).timestamp()

            if backup_time < cutoff_date:
                self.delete_backup(backup["path"])
                removed.append(backup["path"])

        return removed

    def _parse_backup_filename(self, backup_path: Path) -> dict[str, Any]:
        """Parse information from backup filename."""
        # Expected format: instance_db_YYYYMMDD_HHMMSS.dump
        name = backup_path.stem  # Remove .dump extension

        parts = name.split("_")
        if len(parts) >= 3:
            instance = parts[0]
            # Reconstruct db name (might have underscores)
            db_parts = []
            for part in parts[1:-2]:
                db_parts.append(part)
            db_name = "_".join(db_parts)

            # Parse date/time
            date_time = parts[-2] + "_" + parts[-1]

            return {
                "instance": instance,
                "database": db_name,
                "date": date_time,
                "filename": backup_path.name,
            }

        # Fallback
        return {
            "instance": "unknown",
            "database": "unknown",
            "date": "unknown",
            "filename": backup_path.name,
        }

    def _record_backup(self, instance_name: str, db_name: str, backup_path: Path) -> None:
        """Record backup metadata (placeholder for future implementation)."""
        # This could be expanded to store metadata in a separate file
        pass

    def get_backup_dir(self) -> Path:
        """Get the backup directory path."""
        return self.backup_dir

    def backup_database(self, environment: str) -> Path:
        """Backup database for an environment.

        Args:
            environment: Environment name (treats as instance name).

        Returns:
            Path to created backup.
        """
        return self.create_backup(environment)
