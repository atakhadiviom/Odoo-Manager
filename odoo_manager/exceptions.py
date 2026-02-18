"""
Custom exceptions for Odoo Manager.
"""


class OdooManagerError(Exception):
    """Base exception for all Odoo Manager errors."""

    pass


class ConfigError(OdooManagerError):
    """Raised when there is an error with configuration."""

    pass


class InstanceNotFoundError(OdooManagerError):
    """Raised when an instance is not found."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Instance '{name}' not found")


class InstanceAlreadyExistsError(OdooManagerError):
    """Raised when trying to create an instance that already exists."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Instance '{name}' already exists")


class InstanceStateError(OdooManagerError):
    """Raised when an instance is in an invalid state for an operation."""

    pass


class DatabaseError(OdooManagerError):
    """Raised when there is an error with database operations."""

    pass


class DatabaseNotFoundError(OdooManagerError):
    """Raised when a database is not found."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Database '{name}' not found")


class ModuleError(OdooManagerError):
    """Raised when there is an error with module operations."""

    pass


class ModuleNotFoundError(OdooManagerError):
    """Raised when a module is not found."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Module '{name}' not found")


class BackupError(OdooManagerError):
    """Raised when there is an error with backup operations."""

    pass


class DeploymentError(OdooManagerError):
    """Raised when there is an error with deployment operations."""

    pass


class DockerError(OdooManagerError):
    """Raised when there is an error with Docker operations."""

    pass


class PostgresConnectionError(OdooManagerError):
    """Raised when there is an error connecting to PostgreSQL."""

    pass


class RPCError(OdooManagerError):
    """Raised when there is an error with Odoo RPC operations."""

    pass


class GitError(OdooManagerError):
    """Raised when there is an error with Git operations."""

    pass


class EnvironmentNotFoundError(OdooManagerError):
    """Raised when an environment is not found."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Environment '{name}' not found")


class UserNotFoundError(OdooManagerError):
    """Raised when a user is not found."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"User '{name}' not found")


class SSHError(OdooManagerError):
    """Raised when there is an error with SSH operations."""

    pass


class SSLError(OdooManagerError):
    """Raised when there is an error with SSL operations."""

    pass


class SchedulerError(OdooManagerError):
    """Raised when there is an error with scheduler operations."""

    pass
