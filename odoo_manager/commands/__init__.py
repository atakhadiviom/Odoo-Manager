"""CLI command modules."""

from odoo_manager.commands.instance import instance_cli
from odoo_manager.commands.db import db_cli
from odoo_manager.commands.module import module_cli
from odoo_manager.commands.backup import backup_cli
from odoo_manager.commands.logs import logs_cli
from odoo_manager.commands.config import config_cli
from odoo_manager.commands.shell import shell_cmd
from odoo_manager.commands.git import git_cli
from odoo_manager.commands.environment import env_cli
from odoo_manager.commands.deploy import deploy_cli
from odoo_manager.commands.monitor import monitor_cli
from odoo_manager.commands.scheduler import scheduler_cli
from odoo_manager.commands.ssh import ssh_cli
from odoo_manager.commands.user import user_cli
from odoo_manager.commands.ssl import ssl_cli

__all__ = [
    "instance_cli",
    "db_cli",
    "module_cli",
    "backup_cli",
    "logs_cli",
    "config_cli",
    "shell_cmd",
    "git_cli",
    "env_cli",
    "deploy_cli",
    "monitor_cli",
    "scheduler_cli",
    "ssh_cli",
    "user_cli",
    "ssl_cli",
]
