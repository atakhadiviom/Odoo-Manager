"""
Module management for Odoo instances.

Handles listing, installing, uninstalling, and updating modules.
"""

import subprocess
from typing import Optional

from odoo_manager.instance import Instance


class ModuleManager:
    """Manage Odoo modules for an instance."""

    def __init__(self, instance: Instance):
        self.instance = instance

    def list_modules(self, installed_only: bool = False) -> list[dict]:
        """List modules from the instance database.

        Args:
            installed_only: If True, only return installed modules

        Returns:
            List of module dictionaries with name, version, state, etc.
        """
        docker_cmd = self.instance._get_docker_cmd()

        # Query the database using psql
        cmd = docker_cmd + ["exec", self.instance.db_container_name,
                           "psql", "-U", self.instance.config.db_user,
                           "-d", self.instance.config.db_name,
                           "-c", "SELECT name, state, latest_version FROM ir_module_module ORDER BY name"]

        if installed_only:
            cmd[-1] = cmd[-1].replace("ORDER BY name", "WHERE state = 'installed' ORDER BY name")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return []

        modules = []
        lines = result.stdout.strip().split("\n")[2:]  # Skip header and separator
        for line in lines:
            parts = line.split("|")
            if len(parts) >= 3:
                modules.append({
                    "name": parts[0].strip(),
                    "state": parts[1].strip(),
                    "version": parts[2].strip(),
                })

        return modules

    def install(self, module_names: list[str]) -> str:
        """Install modules on the instance.

        Args:
            module_names: List of module names to install

        Returns:
            Output from the installation command
        """
        docker_cmd = self.instance._get_docker_cmd()

        # Use odoo-bin to install modules
        modules = ",".join(module_names)
        cmd = docker_cmd + ["exec", self.instance.container_name,
                           "odoo-bin", "-c", "/etc/odoo/odoo.conf",
                           "-d", self.instance.config.db_name,
                           "-i", modules,
                           "--stop-after-init"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr

    def uninstall(self, module_names: list[str]) -> str:
        """Uninstall modules from the instance.

        Args:
            module_names: List of module names to uninstall

        Returns:
            Output from the uninstallation command
        """
        docker_cmd = self.instance._get_docker_cmd()

        modules = ",".join(module_names)
        cmd = docker_cmd + ["exec", self.instance.container_name,
                           "odoo-bin", "-c", "/etc/odoo/odoo.conf",
                           "-d", self.instance.config.db_name,
                           "--uninstall", modules,
                           "--stop-after-init"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr

    def update(self, module_names: Optional[list[str]] = None) -> str:
        """Update modules on the instance.

        Args:
            module_names: List of module names to update, or None for all

        Returns:
            Output from the update command
        """
        docker_cmd = self.instance._get_docker_cmd()

        if module_names:
            modules = ",".join(module_names)
            cmd = docker_cmd + ["exec", self.instance.container_name,
                               "odoo-bin", "-c", "/etc/odoo/odoo.conf",
                               "-d", self.instance.config.db_name,
                               "-u", modules,
                               "--stop-after-init"]
        else:
            # Update all modules
            cmd = docker_cmd + ["exec", self.instance.container_name,
                               "odoo-bin", "-c", "/etc/odoo/odoo.conf",
                               "-d", self.instance.config.db_name,
                               "-u", "all",
                               "--stop-after-init"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr

    def search(self, query: str) -> list[dict]:
        """Search for modules by name.

        Args:
            query: Search query string

        Returns:
            List of matching modules
        """
        all_modules = self.list_modules()
        query_lower = query.lower()

        return [
            m for m in all_modules
            if query_lower in m["name"].lower()
        ]
