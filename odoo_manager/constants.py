"""
Constants and default values for Odoo Manager.
"""

from pathlib import Path

# Version
__version__ = "0.1.0"

# Default paths
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "odoo-manager"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
DEFAULT_INSTANCES_FILE = DEFAULT_CONFIG_DIR / "instances.yaml"
DEFAULT_DATA_DIR = Path.home() / "odoo-manager" / "data"
DEFAULT_BACKUP_DIR = Path.home() / "odoo-manager" / "backups"
DEFAULT_LOG_DIR = Path.home() / "odoo-manager" / "logs"

# Odoo defaults
DEFAULT_ODOO_VERSION = "master"
DEFAULT_ODOO_PORT = 8069
DEFAULT_ODOO_WORKERS = 4
DEFAULT_ODOO_MAX_CRON_THREADS = 2
DEFAULT_ODOO_DB_MAXCONN = 64

# Docker defaults
DEFAULT_DOCKER_IMAGE = "odoo:latest"
DEFAULT_POSTGRES_IMAGE = "postgres:15"
DEFAULT_POSTGRES_PORT = 5432
DEFAULT_POSTGRES_USER = "odoo"
DEFAULT_POSTGRES_PASSWORD = "odoo"
DEFAULT_POSTGRES_DB = "postgres"

# Editions
EDITION_COMMUNITY = "community"
EDITION_ENTERPRISE = "enterprise"
ALL_EDITIONS = [EDITION_COMMUNITY, EDITION_ENTERPRISE]

# Deployment types
DEPLOYMENT_DOCKER = "docker"
DEPLOYMENT_SOURCE = "source"
ALL_DEPLOYMENTS = [DEPLOYMENT_DOCKER, DEPLOYMENT_SOURCE]

# Instance states
STATE_RUNNING = "running"
STATE_STOPPED = "stopped"
STATE_ERROR = "error"
STATE_UNKNOWN = "unknown"
ALL_STATES = [STATE_RUNNING, STATE_STOPPED, STATE_ERROR, STATE_UNKNOWN]

# Backup defaults
DEFAULT_RETENTION_DAYS = 30
DEFAULT_BACKUP_FORMAT = "dump"  # dump, zip

# File extensions
BACKUP_EXT_DUMP = ".dump"
BACKUP_EXT_ZIP = ".zip"

# Odoo module states
MODULE_STATE_INSTALLED = "installed"
MODULE_STATE_UNINSTALLED = "uninstalled"
MODULE_STATE_TO_INSTALL = "to install"
MODULE_STATE_TO_UPGRADE = "to upgrade"
MODULE_STATE_TO_REMOVE = "to remove"
ALL_MODULE_STATES = [
    MODULE_STATE_INSTALLED,
    MODULE_STATE_UNINSTALLED,
    MODULE_STATE_TO_INSTALL,
    MODULE_STATE_TO_UPGRADE,
    MODULE_STATE_TO_REMOVE,
]

# RPC defaults
DEFAULT_RPC_TIMEOUT = 30
DEFAULT_RPC_PORT = 8069
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"

# Log levels
LOG_LEVEL_DEBUG = "debug"
LOG_LEVEL_INFO = "info"
LOG_LEVEL_WARN = "warn"
LOG_LEVEL_ERROR = "error"
ALL_LOG_LEVELS = [LOG_LEVEL_DEBUG, LOG_LEVEL_INFO, LOG_LEVEL_WARN, LOG_LEVEL_ERROR]

# Git
DEFAULT_GIT_REPOS_DIR = Path.home() / "odoo-manager" / "repos"

# Environment tiers
ENV_TIER_DEV = "dev"
ENV_TIER_STAGING = "staging"
ENV_TIER_PRODUCTION = "production"
ALL_ENV_TIERS = [ENV_TIER_DEV, ENV_TIER_STAGING, ENV_TIER_PRODUCTION]

# User roles
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
ALL_ROLES = [ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER]

# Scheduler
SCHEDULER_PID_FILE = DEFAULT_CONFIG_DIR / "scheduler.pid"
SCHEDULER_LOG_FILE = DEFAULT_LOG_DIR / "scheduler.log"

# SSL
DEFAULT_SSL_CERT_DIR = Path.home() / "odoo-manager" / "ssl"
DEFAULT_NGINX_PORT = 443
DEFAULT_NGINX_HTTP_PORT = 80
