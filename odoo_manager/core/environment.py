"""
Environment management for Odoo Manager.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from odoo_manager.config import EnvironmentConfig, EnvironmentsConfig, InstancesConfig
from odoo_manager.constants import (
    DEFAULT_CONFIG_DIR,
    ENV_TIER_DEV,
    ENV_TIER_PRODUCTION,
    ENV_TIER_STAGING,
)
from odoo_manager.core.git import GitManager, GitRepoInfo
from odoo_manager.core.instance import Instance, InstanceManager
from odoo_manager.exceptions import EnvironmentNotFoundError, GitError
from odoo_manager.utils.output import success, info, warn, error


class EnvironmentTier(str, Enum):
    """Environment tier levels."""

    DEV = ENV_TIER_DEV
    STAGING = ENV_TIER_STAGING
    PRODUCTION = ENV_TIER_PRODUCTION


@dataclass
class DeploymentHistory:
    """Record of a deployment to an environment."""

    id: str
    environment: str
    branch: str
    commit: str
    author: str
    timestamp: datetime
    status: str = "success"
    message: str = ""
    rollback_from: Optional[str] = None


@dataclass
class EnvironmentStatus:
    """Status information for an environment."""

    name: str
    tier: str
    instance_name: Optional[str] = None
    instance_status: Optional[str] = None
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    git_dirty: bool = False
    last_deployment: Optional[DeploymentHistory] = None
    can_promote_to: Optional[str] = None


class EnvironmentManager:
    """Manages deployment environments."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the environment manager.

        Args:
            config_path: Path to configuration directory.
        """
        self.config_path = config_path or DEFAULT_CONFIG_DIR
        self.environments_file = self.config_path / "environments.yaml"
        self.git_manager = GitManager()
        self.instance_manager = InstanceManager(config_path)

    def load_environments(self) -> EnvironmentsConfig:
        """Load environments configuration."""
        if not self.environments_file.exists():
            return EnvironmentsConfig()

        import yaml

        try:
            with open(self.environments_file, "r") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            error(f"Error loading environments: {e}")
            return EnvironmentsConfig()

        if "environments" not in data:
            data = {"environments": data}

        try:
            return EnvironmentsConfig(**data)
        except Exception as e:
            error(f"Error validating environments: {e}")
            return EnvironmentsConfig()

    def save_environments(self, config: EnvironmentsConfig) -> None:
        """Save environments configuration."""
        import yaml

        self.environments_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.environments_file, "w") as f:
            yaml.dump(
                config.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    def create_environment(
        self,
        name: str,
        tier: str = ENV_TIER_DEV,
        workers: int = 4,
        port: int = 8069,
        **kwargs,
    ) -> EnvironmentConfig:
        """Create a new environment.

        Args:
            name: Environment name.
            tier: Environment tier (dev, staging, production).
            workers: Number of Odoo workers.
            port: Port for Odoo.
            **kwargs: Additional environment configuration.

        Returns:
            Created EnvironmentConfig.

        Raises:
            ValueError: If environment already exists.
        """
        config = self.load_environments()

        if config.get_environment(name):
            raise ValueError(f"Environment '{name}' already exists")

        env_config = EnvironmentConfig(
            name=name,
            tier=tier,
            workers=workers,
            port=port,
            **kwargs,
        )

        config.add_environment(env_config)
        self.save_environments(config)

        success(f"Environment '{name}' created")
        return env_config

    def get_environment(self, name: str) -> EnvironmentConfig:
        """Get an environment by name.

        Args:
            name: Environment name.

        Returns:
            EnvironmentConfig.

        Raises:
            EnvironmentNotFoundError: If environment not found.
        """
        config = self.load_environments()
        env = config.get_environment(name)

        if not env:
            raise EnvironmentNotFoundError(name)

        return env

    def list_environments(self, tier: Optional[str] = None) -> list[EnvironmentConfig]:
        """List all environments.

        Args:
            tier: Filter by tier if specified.

        Returns:
            List of EnvironmentConfig objects.
        """
        config = self.load_environments()

        if tier:
            return config.get_by_tier(tier)

        return config.list_environments()

    def remove_environment(self, name: str) -> None:
        """Remove an environment.

        Args:
            name: Environment name.
        """
        config = self.load_environments()
        config.remove_environment(name)
        self.save_environments(config)

        success(f"Environment '{name}' removed")

    def get_status(self, name: str) -> EnvironmentStatus:
        """Get status of an environment.

        Args:
            name: Environment name.

        Returns:
            EnvironmentStatus with current state.
        """
        env = self.get_environment(name)

        # Find associated instance
        instance = None
        instances_config = self.instance_manager.instances_file.load()
        for instance_config in instances_config.list_instances():
            if instance_config.environment == name:
                instance = Instance(
                    instance_config, self.instance_manager.config.settings.data_dir
                )
                break

        status = EnvironmentStatus(
            name=name,
            tier=env.tier,
            instance_name=instance.config.name if instance else None,
            instance_status=instance.status() if instance else None,
        )

        # Git info
        if env.git_repo:
            try:
                repo_info = self.git_manager.get_status(env.git_repo)
                status.git_branch = repo_info.branch
                status.git_commit = repo_info.commit
                status.git_dirty = repo_info.dirty
            except GitError:
                pass

        # Last deployment info
        status.last_deployment = self._get_last_deployment(name)

        # Can promote to
        status.can_promote_to = self._get_next_tier(env.tier)

        return status

    def deploy(
        self,
        environment: str,
        branch: str,
        repo: Optional[str] = None,
        auto_start: bool = True,
    ) -> DeploymentHistory:
        """Deploy a branch to an environment.

        Args:
            environment: Target environment name.
            branch: Git branch to deploy.
            repo: Repository name (uses env default if not specified).
            auto_start: Start instance after deployment.

        Returns:
            DeploymentHistory record.
        """
        env = self.get_environment(environment)

        # Determine repo
        repo_name = repo or env.git_repo
        if not repo_name:
            raise ValueError(
                f"No repository specified for environment '{environment}'"
            )

        # Checkout branch
        info(f"Checking out branch '{branch}' in repo '{repo_name}'...")
        self.git_manager.checkout(repo_name, branch)

        # Pull latest
        info(f"Pulling latest changes...")
        self.git_manager.pull(repo_name, branch=branch)

        # Get commit info
        repo_info = self.git_manager.get_status(repo_name)

        # Find or create instance
        instance = self._get_instance_for_environment(environment)

        # Update instance config
        instances_config = self.instance_manager.instances_file.load()
        instance_config = instances_config.get_instance(instance.config.name)

        if instance_config:
            instance_config.git_branch = branch
            instance_config.git_repo = repo_name
            self.instance_manager.instances_file.save(instances_config)

        # Restart instance if running
        if instance.is_running():
            info(f"Restarting instance '{instance.config.name}'...")
            instance.restart()

        # Record deployment
        history = DeploymentHistory(
            id=f"{environment}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            environment=environment,
            branch=branch,
            commit=repo_info.commit or "unknown",
            author=repo_info.author or "unknown",
            timestamp=datetime.now(),
            status="success",
        )

        self._record_deployment(history)

        success(f"Deployed branch '{branch}' to environment '{environment}'")
        return history

    def promote(
        self,
        source_env: str,
        target_env: Optional[str] = None,
    ) -> DeploymentHistory:
        """Promote from one environment to the next tier.

        Args:
            source_env: Source environment name.
            target_env: Target environment name (auto-detect if None).

        Returns:
            DeploymentHistory record.
        """
        source = self.get_environment(source_env)
        source_status = self.get_status(source_env)

        if not source_status.git_branch:
            raise ValueError(f"No branch deployed to '{source_env}'")

        # Determine target
        if target_env is None:
            target_env = self._get_next_tier(source.tier)

        if not target_env:
            raise ValueError(f"Cannot promote from tier '{source.tier}'")

        target = self.get_environment(target_env)

        # Verify tier progression
        tier_order = [ENV_TIER_DEV, ENV_TIER_STAGING, ENV_TIER_PRODUCTION]
        source_idx = tier_order.index(source.tier)
        target_idx = tier_order.index(target.tier)

        if target_idx <= source_idx:
            raise ValueError(
                f"Cannot promote from {source.tier} to {target.tier} (must move forward)"
            )

        info(f"Promoting '{source_env}' -> '{target_env}'...")

        # Deploy the same branch
        return self.deploy(
            environment=target_env,
            branch=source_status.git_branch,
            repo=source.git_repo,
        )

    def should_auto_deploy(self, environment: str, branch: str) -> bool:
        """Check if a branch should be auto-deployed to an environment.

        Args:
            environment: Environment name.
            branch: Git branch name.

        Returns:
            True if branch matches auto-deploy rules.
        """
        try:
            env = self.get_environment(environment)
        except EnvironmentNotFoundError:
            return False

        for pattern in env.auto_deploy_branches:
            if self._match_branch_pattern(branch, pattern):
                return True

        return False

    def get_deployment_history(
        self, environment: str, limit: int = 10
    ) -> list[DeploymentHistory]:
        """Get deployment history for an environment.

        Args:
            environment: Environment name.
            limit: Maximum number of records.

        Returns:
            List of DeploymentHistory records.
        """
        history_file = self.config_path / "deployment_history.yaml"

        if not history_file.exists():
            return []

        import yaml

        with open(history_file, "r") as f:
            data = yaml.safe_load(f) or {}

        records = []
        for item in data.get(environment, []):
            records.append(
                DeploymentHistory(
                    id=item["id"],
                    environment=item["environment"],
                    branch=item["branch"],
                    commit=item["commit"],
                    author=item["author"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    status=item.get("status", "success"),
                    message=item.get("message", ""),
                    rollback_from=item.get("rollback_from"),
                )
            )

        # Sort by timestamp descending
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[:limit]

    def _get_instance_for_environment(self, environment: str) -> Instance:
        """Get or create instance for an environment."""
        instances_config = self.instance_manager.instances_file.load()

        # Find existing instance
        for instance_config in instances_config.list_instances():
            if instance_config.environment == environment:
                return Instance(
                    instance_config, self.instance_manager.config.settings.data_dir
                )

        # Create new instance
        env = self.get_environment(environment)

        instance_config = self.instance_manager.create_instance(
            name=f"odoo-{environment}",
            db_name=f"odoo_{environment}",
            port=env.port,
            workers=env.workers,
            deployment_type="docker",
        )

        # Update with environment info
        instances_config = self.instance_manager.instances_file.load()
        instance_config = instances_config.get_instance(instance_config.config.name)
        instance_config.environment = environment
        self.instance_manager.instances_file.save(instances_config)

        return Instance(instance_config, self.instance_manager.config.settings.data_dir)

    def _get_next_tier(self, current_tier: str) -> Optional[str]:
        """Get the next environment tier."""
        tier_order = [ENV_TIER_DEV, ENV_TIER_STAGING, ENV_TIER_PRODUCTION]

        try:
            idx = tier_order.index(current_tier)
            if idx + 1 < len(tier_order):
                return tier_order[idx + 1]
        except ValueError:
            pass

        return None

    def _match_branch_pattern(self, branch: str, pattern: str) -> bool:
        """Check if branch matches a pattern."""
        import fnmatch

        return fnmatch.fnmatch(branch, pattern)

    def _record_deployment(self, history: DeploymentHistory) -> None:
        """Record deployment to history file."""
        history_file = self.config_path / "deployment_history.yaml"

        import yaml

        if history_file.exists():
            with open(history_file, "r") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        if history.environment not in data:
            data[history.environment] = []

        data[history.environment].append(
            {
                "id": history.id,
                "environment": history.environment,
                "branch": history.branch,
                "commit": history.commit,
                "author": history.author,
                "timestamp": history.timestamp.isoformat(),
                "status": history.status,
                "message": history.message,
                "rollback_from": history.rollback_from,
            }
        )

        # Keep only last 50
        data[history.environment] = data[history.environment][-50:]

        with open(history_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def _get_last_deployment(self, environment: str) -> Optional[DeploymentHistory]:
        """Get the most recent deployment for an environment."""
        history = self.get_deployment_history(environment, limit=1)
        return history[0] if history else None
