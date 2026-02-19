"""
Base class for deployment strategies.
"""

import os
import stat
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from odoo_manager.config import InstanceConfig
from odoo_manager.constants import STATE_RUNNING, STATE_STOPPED, STATE_UNKNOWN


class BaseDeployer(ABC):
    """Abstract base class for deployment strategies."""

    def __init__(self, instance: InstanceConfig, data_dir: Path):
        self.instance = instance
        self.data_dir = data_dir / instance.name

    @abstractmethod
    def create(self) -> None:
        """Create the instance deployment."""

    @abstractmethod
    def start(self) -> None:
        """Start the instance."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the instance."""

    @abstractmethod
    def restart(self) -> None:
        """Restart the instance."""

    @abstractmethod
    def status(self) -> str:
        """Get the current status of the instance."""
        return STATE_UNKNOWN

    @abstractmethod
    def is_running(self) -> bool:
        """Check if the instance is running."""
        return False

    @abstractmethod
    def remove(self) -> None:
        """Remove the instance deployment."""

    @abstractmethod
    def exec_command(self, command: list[str], capture: bool = False) -> str | int:
        """Execute a command in the instance context."""

    @abstractmethod
    def get_logs(self, follow: bool = False, tail: int = 100) -> str:
        """Get logs from the instance."""

    def get_instance_dir(self) -> Path:
        """Get the instance data directory."""
        return self.data_dir

    def ensure_data_dir(self) -> None:
        """Ensure the instance data directory exists and is writable."""
        # If directory exists but is not writable, fix permissions
        if self.data_dir.exists():
            if not os.access(self.data_dir, os.W_OK):
                # Directory exists but we can't write to it - fix ownership
                try:
                    user = os.environ.get("USER", os.environ.get("USERNAME", "ubuntu"))
                    subprocess.run(
                        ["sudo", "chown", "-R", f"{user}:{user}", str(self.data_dir)],
                        check=True,
                        capture_output=True
                    )
                except subprocess.CalledProcessError:
                    pass  # Will fail on write, let the caller handle it
        else:
            # Create parent directories first
            parent = self.data_dir.parent
            if not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)

            # Check if parent is writable
            if not os.access(parent, os.W_OK):
                # Parent exists but not writable - fix ownership
                try:
                    user = os.environ.get("USER", os.environ.get("USERNAME", "ubuntu"))
                    subprocess.run(
                        ["sudo", "chown", "-R", f"{user}:{user}", str(parent)],
                        check=True,
                        capture_output=True
                    )
                except subprocess.CalledProcessError:
                    pass

        self.data_dir.mkdir(parents=True, exist_ok=True)
