"""
User management for Odoo Manager.
"""

import hashlib
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from odoo_manager.config import UsersConfig, UserConfig
from odoo_manager.constants import (
    ALL_ROLES,
    DEFAULT_CONFIG_DIR,
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
from odoo_manager.exceptions import UserNotFoundError
from odoo_manager.utils.output import info, warn, error


@dataclass
class Session:
    """User session."""

    user_id: str
    username: str
    role: str
    created_at: datetime
    expires_at: datetime
    token: str


class UserManager:
    """Manages users for Odoo Manager."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the user manager.

        Args:
            config_dir: Configuration directory.
        """
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.users_file = self.config_dir / "users.yaml"
        self.sessions: dict[str, Session] = {}

    def load_users(self) -> UsersConfig:
        """Load users configuration."""
        if not self.users_file.exists():
            return UsersConfig()

        import yaml

        try:
            with open(self.users_file, "r") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            error(f"Error loading users: {e}")
            return UsersConfig()

        if "users" not in data:
            data = {"users": data}

        try:
            return UsersConfig(**data)
        except Exception as e:
            error(f"Error validating users: {e}")
            return UsersConfig()

    def save_users(self, config: UsersConfig) -> None:
        """Save users configuration."""
        import yaml

        self.users_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.users_file, "w") as f:
            yaml.dump(
                config.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    def create_user(
        self,
        name: str,
        password: Optional[str] = None,
        role: str = ROLE_VIEWER,
        instances: Optional[list[str]] = None,
        environments: Optional[list[str]] = None,
        permissions: Optional[list[str]] = None,
    ) -> UserConfig:
        """Create a new user.

        Args:
            name: Username.
            password: Password (auto-generated if None).
            role: User role.
            instances: List of allowed instances.
            environments: List of allowed environments.
            permissions: Additional permissions.

        Returns:
            Created UserConfig.
        """
        config = self.load_users()

        if config.get_user(name):
            raise ValueError(f"User '{name}' already exists")

        # Generate password if not provided
        if password is None:
            password = secrets.token_urlsafe(16)
            info(f"Generated password for '{name}': {password}")

        # Hash password
        password_hash = self._hash_password(password)

        user_config = UserConfig(
            name=name,
            role=role,
            instances=instances or [],
            environments=environments or [],
            permissions=permissions or [],
        )

        # Store password hash separately (not in UserConfig)
        self._store_password_hash(name, password_hash)

        config.add_user(user_config)
        self.save_users(config)

        return user_config

    def get_user(self, name: str) -> UserConfig:
        """Get a user by name.

        Args:
            name: Username.

        Returns:
            UserConfig.

        Raises:
            UserNotFoundError: If user not found.
        """
        config = self.load_users()
        user = config.get_user(name)

        if not user:
            raise UserNotFoundError(name)

        return user

    def list_users(self) -> list[UserConfig]:
        """List all users.

        Returns:
            List of UserConfig objects.
        """
        config = self.load_users()
        return config.list_users()

    def remove_user(self, name: str) -> None:
        """Remove a user.

        Args:
            name: Username.
        """
        config = self.load_users()
        config.remove_user(name)
        self.save_users(config)

        # Remove password hash
        self._remove_password_hash(name)

    def authenticate(self, name: str, password: str) -> Optional[Session]:
        """Authenticate a user.

        Args:
            name: Username.
            password: Password.

        Returns:
            Session if authentication successful, None otherwise.
        """
        try:
            user = self.get_user(name)
        except UserNotFoundError:
            return None

        # Verify password
        stored_hash = self._get_password_hash(name)
        if not stored_hash:
            return None

        password_hash = self._hash_password(password)

        if not secrets.compare_digest(password_hash, stored_hash):
            return None

        # Create session
        session = Session(
            user_id=name,
            username=name,
            role=user.role,
            created_at=datetime.now(),
            expires_at=datetime.now(),
            token=secrets.token_urlsafe(32),
        )

        self.sessions[session.token] = session

        return session

    def get_session(self, token: str) -> Optional[Session]:
        """Get session by token.

        Args:
            token: Session token.

        Returns:
            Session or None.
        """
        return self.sessions.get(token)

    def set_role(self, name: str, role: str) -> None:
        """Set user role.

        Args:
            name: Username.
            role: New role.
        """
        if role not in ALL_ROLES:
            raise ValueError(f"Invalid role: {role}")

        config = self.load_users()
        user = config.get_user(name)

        if not user:
            raise UserNotFoundError(name)

        user.role = role
        self.save_users(config)

    def grant_permission(self, name: str, permission: str) -> None:
        """Grant permission to user.

        Args:
            name: Username.
            permission: Permission to grant.
        """
        config = self.load_users()
        user = config.get_user(name)

        if not user:
            raise UserNotFoundError(name)

        if permission not in user.permissions:
            user.permissions.append(permission)

        self.save_users(config)

    def revoke_permission(self, name: str, permission: str) -> None:
        """Revoke permission from user.

        Args:
            name: Username.
            permission: Permission to revoke.
        """
        config = self.load_users()
        user = config.get_user(name)

        if not user:
            raise UserNotFoundError(name)

        if permission in user.permissions:
            user.permissions.remove(permission)

        self.save_users(config)

    def allow_instance(self, name: str, instance: str) -> None:
        """Allow user to access an instance.

        Args:
            name: Username.
            instance: Instance name.
        """
        config = self.load_users()
        user = config.get_user(name)

        if not user:
            raise UserNotFoundError(name)

        if instance not in user.instances:
            user.instances.append(instance)

        self.save_users(config)

    def deny_instance(self, name: str, instance: str) -> None:
        """Deny user access to an instance.

        Args:
            name: Username.
            instance: Instance name.
        """
        config = self.load_users()
        user = config.get_user(name)

        if not user:
            raise UserNotFoundError(name)

        if instance in user.instances:
            user.instances.remove(instance)

        self.save_users(config)

    def allow_environment(self, name: str, environment: str) -> None:
        """Allow user to access an environment.

        Args:
            name: Username.
            environment: Environment name.
        """
        config = self.load_users()
        user = config.get_user(name)

        if not user:
            raise UserNotFoundError(name)

        if environment not in user.environments:
            user.environments.append(environment)

        self.save_users(config)

    def deny_environment(self, name: str, environment: str) -> None:
        """Deny user access to an environment.

        Args:
            name: Username.
            environment: Environment name.
        """
        config = self.load_users()
        user = config.get_user(name)

        if not user:
            raise UserNotFoundError(name)

        if environment in user.environments:
            user.environments.remove(environment)

        self.save_users(config)

    def check_permission(
        self, session: Session, permission: str, instance: Optional[str] = None, environment: Optional[str] = None
    ) -> bool:
        """Check if session has permission.

        Args:
            session: User session.
            permission: Permission to check.
            instance: Optional instance to check.
            environment: Optional environment to check.

        Returns:
            True if permitted.
        """
        # Admin has all permissions
        if session.role == ROLE_ADMIN:
            return True

        # Check explicit permission
        user = self.get_user(session.username)
        if permission in user.permissions:
            return True

        # Check instance access
        if instance and instance not in user.instances:
            return False

        # Check environment access
        if environment and environment not in user.environments:
            return False

        # Role-based permissions
        if session.role == ROLE_VIEWER:
            viewer_permissions = ["instance:read", "db:read", "module:read"]
            return permission in viewer_permissions

        if session.role == ROLE_OPERATOR:
            operator_permissions = [
                "instance:read",
                "instance:start",
                "instance:stop",
                "instance:restart",
                "db:read",
                "db:create",
                "db:backup",
                "module:read",
                "module:install",
            ]
            return permission in operator_permissions

        return False

    def _hash_password(self, password: str) -> str:
        """Hash a password."""
        return hashlib.sha256(password.encode()).hexdigest()

    def _get_password_file(self) -> Path:
        """Get password file path."""
        return self.config_dir / "passwords.yaml"

    def _store_password_hash(self, username: str, password_hash: str) -> None:
        """Store password hash."""
        import yaml

        password_file = self._get_password_file()

        if password_file.exists():
            with open(password_file, "r") as f:
                passwords = yaml.safe_load(f) or {}
        else:
            passwords = {}

        passwords[username] = password_hash

        with open(password_file, "w") as f:
            yaml.dump(passwords, f)

    def _get_password_hash(self, username: str) -> Optional[str]:
        """Get stored password hash."""
        import yaml

        password_file = self._get_password_file()

        if not password_file.exists():
            return None

        with open(password_file, "r") as f:
            passwords = yaml.safe_load(f) or {}

        return passwords.get(username)

    def _remove_password_hash(self, username: str) -> None:
        """Remove password hash."""
        import yaml

        password_file = self._get_password_file()

        if not password_file.exists():
            return

        with open(password_file, "r") as f:
            passwords = yaml.safe_load(f) or {}

        if username in passwords:
            del passwords[username]

        with open(password_file, "w") as f:
            yaml.dump(passwords, f)


class Permission:
    """Permission constants."""

    # Instance permissions
    INSTANCE_READ = "instance:read"
    INSTANCE_CREATE = "instance:create"
    INSTANCE_UPDATE = "instance:update"
    INSTANCE_DELETE = "instance:delete"
    INSTANCE_START = "instance:start"
    INSTANCE_STOP = "instance:stop"
    INSTANCE_RESTART = "instance:restart"

    # Database permissions
    DB_READ = "db:read"
    DB_CREATE = "db:create"
    DB_DELETE = "db:delete"
    DB_BACKUP = "db:backup"
    DB_RESTORE = "db:restore"

    # Module permissions
    MODULE_READ = "module:read"
    MODULE_INSTALL = "module:install"
    MODULE_UNINSTALL = "module:uninstall"
    MODULE_UPDATE = "module:update"

    # Environment permissions
    ENV_READ = "env:read"
    ENV_DEPLOY = "env:deploy"
    ENV_PROMOTE = "env:promote"

    # Backup permissions
    BACKUP_READ = "backup:read"
    BACKUP_CREATE = "backup:create"
    BACKUP_DELETE = "backup:delete"
    BACKUP_SCHEDULE = "backup:schedule"

    # User permissions
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:user"

    # System permissions
    SYSTEM_SSH = "system:ssh"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_CONFIG = "system:config"
