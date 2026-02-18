"""
Instance model and operations.
"""

from pathlib import Path
from typing import Any

from odoo_manager.config import Config, InstanceConfig, InstancesFile
from odoo_manager.constants import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_DATA_DIR,
    STATE_RUNNING,
    STATE_STOPPED,
    DEPLOYMENT_DOCKER,
    DEPLOYMENT_SOURCE,
)
from odoo_manager.deployers.docker import DockerDeployer
from odoo_manager.deployers.source import SourceDeployer
from odoo_manager.exceptions import (
    InstanceAlreadyExistsError,
    InstanceNotFoundError,
    InstanceStateError,
)


class Instance:
    """Represents an Odoo instance with deployment capabilities."""

    def __init__(self, config: InstanceConfig, data_dir: Path | None = None):
        self.config = config
        self.data_dir = data_dir or DEFAULT_DATA_DIR

        # Get the appropriate deployer
        self.deployer = self._get_deployer()

    def _get_deployer(self):
        """Get the deployer based on deployment type."""
        if self.config.deployment_type == DEPLOYMENT_DOCKER:
            return DockerDeployer(self.config, self.data_dir)
        elif self.config.deployment_type == DEPLOYMENT_SOURCE:
            return SourceDeployer(self.config, self.data_dir)
        else:
            raise ValueError(f"Unsupported deployment type: {self.config.deployment_type}")

    def start(self) -> None:
        """Start the instance."""
        self.deployer.start()

    def stop(self) -> None:
        """Stop the instance."""
        self.deployer.stop()

    def restart(self) -> None:
        """Restart the instance."""
        self.deployer.restart()

    def status(self) -> str:
        """Get the status of the instance."""
        return self.deployer.status()

    def is_running(self) -> bool:
        """Check if the instance is running."""
        return self.deployer.is_running()

    def remove(self) -> None:
        """Remove the instance deployment."""
        if self.is_running():
            raise InstanceStateError("Cannot remove running instance. Stop it first.")
        self.deployer.remove()

    def exec_command(self, command: list[str], capture: bool = False) -> str | int:
        """Execute a command in the instance."""
        if not self.is_running():
            raise InstanceStateError("Cannot execute command on stopped instance.")
        return self.deployer.exec_command(command, capture)

    def get_logs(self, follow: bool = False, tail: int = 100) -> str:
        """Get logs from the instance."""
        return self.deployer.get_logs(follow, tail)

    def to_dict(self) -> dict[str, Any]:
        """Convert instance to dictionary."""
        return {
            "name": self.config.name,
            "version": self.config.version,
            "edition": self.config.edition,
            "deployment_type": self.config.deployment_type,
            "port": self.config.port,
            "workers": self.config.workers,
            "db_name": self.config.db_name,
            "status": self.status(),
            "running": self.is_running(),
        }


class InstanceManager:
    """Manages multiple Odoo instances."""

    def __init__(self, config_path: Path | None = None):
        self.config = Config.load(config_path)
        self.instances_file = InstancesFile(config_path or DEFAULT_CONFIG_FILE.parent / "instances.yaml")

    def create_instance(
        self,
        name: str,
        version: str = "17.0",
        edition: str = "community",
        deployment_type: str = DEPLOYMENT_DOCKER,
        port: int = 8069,
        workers: int = 4,
        db_name: str | None = None,
        **kwargs,
    ) -> Instance:
        """Create a new instance."""
        # Check if instance already exists
        instances_config = self.instances_file.load()
        if instances_config.get_instance(name):
            raise InstanceAlreadyExistsError(name)

        # Create instance configuration
        db_name = db_name or name
        instance_config = InstanceConfig(
            name=name,
            version=version,
            edition=edition,
            deployment_type=deployment_type,
            port=port,
            workers=workers,
            db_name=db_name,
            **kwargs,
        )

        # Add to instances file
        instances_config.add_instance(instance_config)
        self.instances_file.save(instances_config)

        # Create instance and deployer
        instance = Instance(instance_config, self.config.settings.data_dir)
        instance.deployer.create()

        return instance

    def get_instance(self, name: str) -> Instance:
        """Get an instance by name."""
        instances_config = self.instances_file.load()
        instance_config = instances_config.get_instance(name)

        if not instance_config:
            raise InstanceNotFoundError(name)

        return Instance(instance_config, self.config.settings.data_dir)

    def list_instances(self) -> list[Instance]:
        """List all instances."""
        instances_config = self.instances_file.load()
        return [
            Instance(config, self.config.settings.data_dir)
            for config in instances_config.list_instances()
        ]

    def remove_instance(self, name: str) -> None:
        """Remove an instance."""
        instance = self.get_instance(name)
        instance.remove()

        # Remove from instances file
        instances_config = self.instances_file.load()
        instances_config.remove_instance(name)
        self.instances_file.save(instances_config)

    def instance_exists(self, name: str) -> bool:
        """Check if an instance exists."""
        instances_config = self.instances_file.load()
        return instances_config.get_instance(name) is not None
