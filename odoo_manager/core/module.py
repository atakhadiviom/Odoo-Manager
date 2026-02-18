"""
Module operations for Odoo instances.
"""

from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

import urllib3

# Suppress only the InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

from odoo_manager.config import InstanceConfig
from odoo_manager.constants import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_RPC_PORT,
    DEFAULT_RPC_TIMEOUT,
    DEPLOYMENT_DOCKER,
)
from odoo_manager.deployers.docker import DockerDeployer
from odoo_manager.exceptions import ModuleError, ModuleNotFoundError, RPCError


class OdooRPCClient:
    """Simple XML-RPC client for Odoo."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = DEFAULT_RPC_PORT,
        database: str = "postgres",
        username: str = DEFAULT_ADMIN_USERNAME,
        password: str = DEFAULT_ADMIN_PASSWORD,
        timeout: int = DEFAULT_RPC_TIMEOUT,
        verify_ssl: bool = False,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.uid = None

        self._base_url = f"http{'s' if verify_ssl else ''}://{host}:{port}"
        self._common_url = f"{self._base_url}/xmlrpc/2/common"
        self._object_url = f"{self._base_url}/xmlrpc/2/object"

    def _get_payload(self, method: str, params: list) -> dict:
        """Create XML-RPC payload."""
        return {
            "jsonrpc": "2.0",
            "method": "call",
            "params": [
                self.database,
                self.uid or "",
                self.password,
                method,
                params,
            ],
            "id": 1,
        }

    def connect(self) -> None:
        """Authenticate with Odoo."""
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "common",
                "method": "login",
                "args": [self.database, self.username, self.password],
            },
            "id": 1,
        }

        try:
            response = requests.post(
                self._common_url,
                json=payload,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            result = response.json()

            if "error" in result:
                raise RPCError(f"Authentication failed: {result['error']}")

            self.uid = result.get("result")

            if not self.uid:
                raise RPCError("Authentication failed: No UID returned")

        except requests.RequestException as e:
            raise RPCError(f"Connection failed: {e}")

    def execute_kw(
        self,
        model: str,
        method: str,
        domain: list | None = None,
        fields: list | None = None,
        kwargs: dict | None = None,
    ) -> Any:
        """Execute an Odoo model method."""
        if self.uid is None:
            self.connect()

        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    self.database,
                    self.uid,
                    self.password,
                    model,
                    method,
                    domain or [],
                    fields or {},
                ],
            },
            "id": 1,
        }

        # Add kwargs if provided
        if kwargs:
            payload["params"]["args"].extend([kwargs])

        try:
            response = requests.post(
                self._object_url,
                json=payload,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            result = response.json()

            if "error" in result:
                error_data = result["error"].get("data", {})
                raise RPCError(f"RPC error: {error_data.get('message', result['error'])}")

            return result.get("result")

        except requests.RequestException as e:
            raise RPCError(f"RPC request failed: {e}")

    def search_read(self, model: str, domain: list = None, fields: list = None) -> list[dict]:
        """Search and read records."""
        return self.execute_kw(model, "search_read", domain, {"fields": fields or []})

    def search(self, model: str, domain: list = None) -> list[int]:
        """Search record IDs."""
        return self.execute_kw(model, "search", domain or [])

    def read(self, model: str, ids: list[int], fields: list = None) -> list[dict]:
        """Read records."""
        return self.execute_kw(model, "read", ids, {"fields": fields or []})


class ModuleManager:
    """Manages modules for an Odoo instance."""

    def __init__(self, instance: InstanceConfig):
        self.instance = instance
        self.rpc_client = OdooRPCClient(
            host="localhost",
            port=instance.port,
            database=instance.db_name,
            username=DEFAULT_ADMIN_USERNAME,
            password=instance.admin_password,
        )

    def list_modules(
        self, state: str | None = None, installed_only: bool = False
    ) -> list[dict[str, Any]]:
        """List all modules, optionally filtered by state."""
        domain = []
        if state:
            domain.append(("state", "=", state))
        elif installed_only:
            domain.append(("state", "=", "installed"))

        fields = ["name", "state", "latest_version", "shortdesc", "author", "summary"]

        try:
            modules = self.rpc_client.search_read("ir.module.module", domain, fields)
            return modules
        except RPCError as e:
            raise ModuleError(f"Failed to list modules: {e}")

    def get_module(self, name: str) -> dict[str, Any] | None:
        """Get information about a specific module."""
        try:
            result = self.rpc_client.search_read(
                "ir.module.module",
                [("name", "=", name)],
                ["name", "state", "latest_version", "shortdesc", "author", "summary", "description"],
            )
            return result[0] if result else None
        except RPCError as e:
            raise ModuleError(f"Failed to get module: {e}")

    def install_module(self, name: str) -> None:
        """Install a module."""
        module = self.get_module(name)

        if not module:
            raise ModuleNotFoundError(name)

        if module["state"] == "installed":
            raise ModuleError(f"Module '{name}' is already installed")

        try:
            # Load the module
            self.rpc_client.execute_kw(
                "ir.module.module",
                "button_immediate_install",
                [[module["id"]]],
            )
        except RPCError as e:
            raise ModuleError(f"Failed to install module '{name}': {e}")

    def uninstall_module(self, name: str) -> None:
        """Uninstall a module."""
        module = self.get_module(name)

        if not module:
            raise ModuleNotFoundError(name)

        if module["state"] != "installed":
            raise ModuleError(f"Module '{name}' is not installed")

        try:
            self.rpc_client.execute_kw(
                "ir.module.module",
                "button_immediate_uninstall",
                [[module["id"]]],
            )
        except RPCError as e:
            raise ModuleError(f"Failed to uninstall module '{name}': {e}")

    def update_module(self, name: str | None = None) -> None:
        """Update a module or all modules."""
        try:
            if name:
                module = self.get_module(name)
                if not module:
                    raise ModuleNotFoundError(name)

                # Upgrade specific module
                self.rpc_client.execute_kw(
                    "ir.module.module",
                    "button_immediate_upgrade",
                    [[module["id"]]],
                )
            else:
                # Upgrade all modules
                self.rpc_client.execute_kw(
                    "base.module.upgrade",
                    "upgrade_module",
                    [[], []],
                )
        except RPCError as e:
            raise ModuleError(f"Failed to update module: {e}")

    def get_module_state(self, name: str) -> str:
        """Get the state of a module."""
        module = self.get_module(name)
        return module["state"] if module else "unknown"
