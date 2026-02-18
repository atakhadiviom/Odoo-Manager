"""
Base class for deployment strategies.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from odoo_manager.config import InstanceConfig
from odoo_manager.constants import STATE_RUNNING, STATE_STOPPED


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
        """Ensure the instance data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
