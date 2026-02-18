"""
Configuration management for Odoo Manager.

Uses Pydantic for validation and YAML for storage.
"""

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

from odoo_manager.constants import (
    ALL_DEPLOYMENTS,
    ALL_EDITIONS,
    ALL_ENV_TIERS,
    ALL_ROLES,
    DEFAULT_BACKUP_DIR,
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    DEFAULT_DATA_DIR,
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_LOG_DIR,
    DEFAULT_POSTGRES_DB,
    DEFAULT_POSTGRES_IMAGE,
    DEFAULT_POSTGRES_PASSWORD,
    DEFAULT_POSTGRES_PORT,
    DEFAULT_POSTGRES_USER,
    EDITION_COMMUNITY,
    EDITION_ENTERPRISE,
    ENV_TIER_DEV,
    ENV_TIER_PRODUCTION,
    ENV_TIER_STAGING,
)
from odoo_manager.exceptions import ConfigError


class EnvironmentConfig(BaseModel):
    """Configuration for a deployment environment."""

    name: str
    tier: str = ENV_TIER_DEV
    auto_deploy_branches: list[str] = Field(default_factory=list)
    workers: int = 4
    db_filter: str = "^%d$"
    port: int = 8069
    git_repo: Optional[str] = None
    git_branch: Optional[str] = None
    env_vars: dict[str, str] = Field(default_factory=dict)
    ssl_enabled: bool = False
    ssl_domain: Optional[str] = None
    backup_schedule: Optional[str] = None

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        if v not in ALL_ENV_TIERS:
            raise ValueError(f"Tier must be one of {ALL_ENV_TIERS}")
        return v


class EnvironmentsConfig(BaseModel):
    """Configuration for all environments."""

    environments: dict[str, EnvironmentConfig] = Field(default_factory=dict)

    def add_environment(self, env: EnvironmentConfig) -> None:
        """Add an environment configuration."""
        self.environments[env.name] = env

    def remove_environment(self, name: str) -> None:
        """Remove an environment configuration."""
        if name in self.environments:
            del self.environments[name]

    def get_environment(self, name: str) -> Optional[EnvironmentConfig]:
        """Get an environment configuration by name."""
        return self.environments.get(name)

    def list_environments(self) -> list[EnvironmentConfig]:
        """List all environment configurations."""
        return list(self.environments.values())

    def get_by_tier(self, tier: str) -> list[EnvironmentConfig]:
        """Get all environments of a specific tier."""
        return [e for e in self.environments.values() if e.tier == tier]


class UserConfig(BaseModel):
    """Configuration for a user."""

    name: str
    role: str = "viewer"
    permissions: list[str] = Field(default_factory=list)
    instances: list[str] = Field(default_factory=list)  # Allowed instances
    environments: list[str] = Field(default_factory=list)  # Allowed environments

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ALL_ROLES:
            raise ValueError(f"Role must be one of {ALL_ROLES}")
        return v


class UsersConfig(BaseModel):
    """Configuration for all users."""

    users: dict[str, UserConfig] = Field(default_factory=dict)

    def add_user(self, user: UserConfig) -> None:
        """Add a user configuration."""
        self.users[user.name] = user

    def remove_user(self, name: str) -> None:
        """Remove a user configuration."""
        if name in self.users:
            del self.users[name]

    def get_user(self, name: str) -> Optional[UserConfig]:
        """Get a user configuration by name."""
        return self.users.get(name)

    def list_users(self) -> list[UserConfig]:
        """List all user configurations."""
        return list(self.users.values())


class PostgresConfig(BaseModel):
    """PostgreSQL configuration."""

    host: str = "localhost"
    port: int = DEFAULT_POSTGRES_PORT
    user: str = DEFAULT_POSTGRES_USER
    password: str = DEFAULT_POSTGRES_PASSWORD
    superuser: str = "postgres"
    image: str = DEFAULT_POSTGRES_IMAGE


class BackupConfig(BaseModel):
    """Backup configuration."""

    retention_days: int = 30
    compression: str = "gzip"
    format: str = "dump"


class SettingsConfig(BaseModel):
    """General settings configuration."""

    data_dir: Path = DEFAULT_DATA_DIR
    backup_dir: Path = DEFAULT_BACKUP_DIR
    log_dir: Path = DEFAULT_LOG_DIR
    default_edition: str = EDITION_COMMUNITY
    default_deployment: str = "docker"
    default_odoo_version: str = "17.0"

    @field_validator("default_edition")
    @classmethod
    def validate_edition(cls, v: str) -> str:
        if v not in ALL_EDITIONS:
            raise ValueError(f"Edition must be one of {ALL_EDITIONS}")
        return v

    @field_validator("default_deployment")
    @classmethod
    def validate_deployment(cls, v: str) -> str:
        if v not in ALL_DEPLOYMENTS:
            raise ValueError(f"Deployment must be one of {ALL_DEPLOYMENTS}")
        return v


class InstanceConfig(BaseModel):
    """Configuration for a single Odoo instance."""

    name: str
    version: str = "17.0"
    edition: str = EDITION_COMMUNITY
    deployment_type: str = "docker"
    port: int = 8069
    workers: int = 4
    max_cron_threads: int = 2
    db_maxconn: int = 64
    db_name: str
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = DEFAULT_POSTGRES_USER
    db_password: str = DEFAULT_POSTGRES_PASSWORD
    db_filter: str = "^%d$"
    addons_path: Optional[str] = None
    without_demo: bool = True
    admin_password: str = "admin"
    image: Optional[str] = None
    postgres_image: str = DEFAULT_POSTGRES_IMAGE
    env_vars: dict[str, str] = Field(default_factory=dict)
    # Extended attributes
    environment: Optional[str] = None
    git_repo: Optional[str] = None
    git_branch: Optional[str] = None
    ssl_enabled: bool = False
    ssl_domain: Optional[str] = None
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None

    @field_validator("edition")
    @classmethod
    def validate_edition(cls, v: str) -> str:
        if v not in ALL_EDITIONS:
            raise ValueError(f"Edition must be one of {ALL_EDITIONS}")
        return v

    @field_validator("deployment_type")
    @classmethod
    def validate_deployment(cls, v: str) -> str:
        if v not in ALL_DEPLOYMENTS:
            raise ValueError(f"Deployment must be one of {ALL_DEPLOYMENTS}")
        return v

    def get_odoo_image(self) -> str:
        """Get the Docker image for Odoo."""
        if self.image:
            return self.image
        edition_suffix = "" if self.edition == EDITION_COMMUNITY else f"-{self.edition}"
        return f"odoo:{self.version}{edition_suffix}"


class InstancesConfig(BaseModel):
    """Configuration for all instances."""

    instances: dict[str, InstanceConfig] = Field(default_factory=dict)

    def add_instance(self, instance: InstanceConfig) -> None:
        """Add an instance configuration."""
        self.instances[instance.name] = instance

    def remove_instance(self, name: str) -> None:
        """Remove an instance configuration."""
        if name in self.instances:
            del self.instances[name]

    def get_instance(self, name: str) -> Optional[InstanceConfig]:
        """Get an instance configuration by name."""
        return self.instances.get(name)

    def list_instances(self) -> list[InstanceConfig]:
        """List all instance configurations."""
        return list(self.instances.values())


class Config(BaseModel):
    """Main configuration model."""

    settings: SettingsConfig = Field(default_factory=SettingsConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)
    instances: InstancesConfig = Field(default_factory=InstancesConfig)
    environments: EnvironmentsConfig = Field(default_factory=EnvironmentsConfig)
    users: UsersConfig = Field(default_factory=UsersConfig)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Load configuration from a YAML file."""
        config_path = path or DEFAULT_CONFIG_FILE

        if not config_path.exists():
            # Return default configuration
            return cls()

        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parsing config file: {e}")

        try:
            return cls(**data)
        except Exception as e:
            raise ConfigError(f"Error validating configuration: {e}")

    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to a YAML file."""
        config_path = path or DEFAULT_CONFIG_FILE

        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.dump(
                self.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )


class InstancesFile:
    """Manages the instances.yaml file separately."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (DEFAULT_CONFIG_DIR / "instances.yaml")

    def load(self) -> InstancesConfig:
        """Load instances configuration from file."""
        if not self.path.exists():
            return InstancesConfig()

        try:
            with open(self.path, "r") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parsing instances file: {e}")

        if "instances" not in data:
            data = {"instances": data}

        try:
            return InstancesConfig(**data)
        except Exception as e:
            raise ConfigError(f"Error validating instances configuration: {e}")

    def save(self, config: InstancesConfig) -> None:
        """Save instances configuration to file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.path, "w") as f:
            yaml.dump(
                config.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
