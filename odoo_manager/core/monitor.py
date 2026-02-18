"""
Health monitoring for Odoo instances.
"""

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import psutil

from odoo_manager.core.instance import Instance, InstanceManager
from odoo_manager.utils.output import info, warn, error


class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    value: Optional[Any] = None
    threshold: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class InstanceHealth:
    """Overall health status for an instance."""

    instance_name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    checks: list[HealthCheckResult] = field(default_factory=list)
    cpu_percent: float = 0.0
    memory_mb: int = 0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    uptime_seconds: int = 0
    last_check: datetime = field(default_factory=datetime.now)


class HealthMonitor:
    """Monitors health of Odoo instances."""

    # Default thresholds for alerts
    DEFAULT_CPU_WARNING = 70.0
    DEFAULT_CPU_CRITICAL = 90.0
    DEFAULT_MEMORY_WARNING = 70.0
    DEFAULT_MEMORY_CRITICAL = 85.0
    DEFAULT_DISK_WARNING = 80.0
    DEFAULT_DISK_CRITICAL = 90.0

    def __init__(
        self,
        cpu_warning: float = DEFAULT_CPU_WARNING,
        cpu_critical: float = DEFAULT_CPU_CRITICAL,
        memory_warning: float = DEFAULT_MEMORY_WARNING,
        memory_critical: float = DEFAULT_MEMORY_CRITICAL,
        disk_warning: float = DEFAULT_DISK_WARNING,
        disk_critical: float = DEFAULT_DISK_CRITICAL,
    ):
        """Initialize the health monitor.

        Args:
            cpu_warning: CPU usage percentage for warning.
            cpu_critical: CPU usage percentage for critical.
            memory_warning: Memory usage percentage for warning.
            memory_critical: Memory usage percentage for critical.
            disk_warning: Disk usage percentage for warning.
            disk_critical: Disk usage percentage for critical.
        """
        self.cpu_warning = cpu_warning
        self.cpu_critical = cpu_critical
        self.memory_warning = memory_warning
        self.memory_critical = memory_warning
        self.disk_warning = disk_warning
        self.disk_critical = disk_critical

    def check_instance(self, instance: Instance) -> InstanceHealth:
        """Perform health check on an instance.

        Args:
            instance: Instance to check.

        Returns:
            InstanceHealth with check results.
        """
        health = InstanceHealth(instance_name=instance.config.name)

        if not instance.is_running():
            health.status = HealthStatus.CRITICAL
            health.checks.append(
                HealthCheckResult(
                    name="Instance Status",
                    status=HealthStatus.CRITICAL,
                    message="Instance is not running",
                )
            )
            return health

        checks = []

        # 1. Container/Process status
        checks.append(self._check_instance_status(instance))

        # 2. Database connectivity
        checks.append(self._check_database(instance))

        # 3. HTTP endpoint
        checks.append(self._check_http_endpoint(instance))

        # 4. Resource usage
        resource_check = self._check_resources(instance)
        checks.append(resource_check)

        health.cpu_percent = resource_check.value.get("cpu", 0.0) if resource_check.value else 0.0
        health.memory_mb = resource_check.value.get("memory_mb", 0) if resource_check.value else 0
        health.memory_percent = (
            resource_check.value.get("memory_percent", 0.0) if resource_check.value else 0.0
        )
        health.disk_percent = (
            resource_check.value.get("disk_percent", 0.0) if resource_check.value else 0.0
        )

        # 5. Log errors
        checks.append(self._check_log_errors(instance))

        health.checks = checks

        # Determine overall status
        if any(c.status == HealthStatus.CRITICAL for c in checks):
            health.status = HealthStatus.CRITICAL
        elif any(c.status == HealthStatus.WARNING for c in checks):
            health.status = HealthStatus.WARNING
        else:
            health.status = HealthStatus.HEALTHY

        health.last_check = datetime.now()

        return health

    def check_all_instances(self) -> list[InstanceHealth]:
        """Check health of all instances.

        Returns:
            List of InstanceHealth for all instances.
        """
        manager = InstanceManager()
        instances = manager.list_instances()

        return [self.check_instance(instance) for instance in instances]

    def check_instance_by_name(self, name: str) -> Optional[InstanceHealth]:
        """Check health of an instance by name.

        Args:
            name: Instance name.

        Returns:
            InstanceHealth or None if instance not found.
        """
        try:
            manager = InstanceManager()
            instance = manager.get_instance(name)
            return self.check_instance(instance)
        except Exception:
            return None

    def _check_instance_status(self, instance: Instance) -> HealthCheckResult:
        """Check if instance is running."""
        try:
            if instance.is_running():
                return HealthCheckResult(
                    name="Instance Status",
                    status=HealthStatus.HEALTHY,
                    message="Instance is running",
                )
            else:
                return HealthCheckResult(
                    name="Instance Status",
                    status=HealthStatus.CRITICAL,
                    message="Instance is not running",
                )
        except Exception as e:
            return HealthCheckResult(
                name="Instance Status",
                status=HealthStatus.UNKNOWN,
                message=f"Error checking status: {e}",
            )

    def _check_database(self, instance: Instance) -> HealthCheckResult:
        """Check database connectivity."""
        try:
            from odoo_manager.utils.postgres import check_connection

            connected = check_connection(
                host=instance.config.db_host,
                port=instance.config.db_port,
                user=instance.config.db_user,
                password=instance.config.db_password,
            )

            if connected:
                return HealthCheckResult(
                    name="Database",
                    status=HealthStatus.HEALTHY,
                    message="Database connection successful",
                )
            else:
                return HealthCheckResult(
                    name="Database",
                    status=HealthStatus.CRITICAL,
                    message="Cannot connect to database",
                )
        except Exception as e:
            return HealthCheckResult(
                name="Database",
                status=HealthStatus.WARNING,
                message=f"Database check error: {e}",
            )

    def _check_http_endpoint(self, instance: Instance) -> HealthCheckResult:
        """Check HTTP endpoint."""
        try:
            import requests

            url = f"http://localhost:{instance.config.port}/web/login"
            response = requests.get(url, timeout=5)

            if response.status_code in (200, 302):
                return HealthCheckResult(
                    name="HTTP Endpoint",
                    status=HealthStatus.HEALTHY,
                    message=f"HTTP endpoint responding ({response.status_code})",
                )
            else:
                return HealthCheckResult(
                    name="HTTP Endpoint",
                    status=HealthStatus.WARNING,
                    message=f"Unexpected status code: {response.status_code}",
                )
        except requests.Timeout:
            return HealthCheckResult(
                name="HTTP Endpoint",
                status=HealthStatus.WARNING,
                message="HTTP endpoint timeout",
            )
        except Exception as e:
            return HealthCheckResult(
                name="HTTP Endpoint",
                status=HealthStatus.UNKNOWN,
                message=f"HTTP check error: {e}",
            )

    def _check_resources(self, instance: Instance) -> HealthCheckResult:
        """Check resource usage."""
        try:
            # Get container stats for Docker deployments
            if instance.config.deployment_type == "docker":
                stats = self._get_docker_stats(instance)
            else:
                # Get system process stats
                stats = self._get_process_stats(instance)

            # Determine status based on thresholds
            status = HealthStatus.HEALTHY
            messages = []

            if stats.get("cpu", 0) >= self.cpu_critical:
                status = HealthStatus.CRITICAL
                messages.append(f"CPU usage critical: {stats['cpu']:.1f}%")
            elif stats.get("cpu", 0) >= self.cpu_warning:
                if status != HealthStatus.CRITICAL:
                    status = HealthStatus.WARNING
                messages.append(f"CPU usage high: {stats['cpu']:.1f}%")

            if stats.get("memory_percent", 0) >= self.memory_critical:
                status = HealthStatus.CRITICAL
                messages.append(f"Memory usage critical: {stats['memory_percent']:.1f}%")
            elif stats.get("memory_percent", 0) >= self.memory_warning:
                if status != HealthStatus.CRITICAL:
                    status = HealthStatus.WARNING
                messages.append(f"Memory usage high: {stats['memory_percent']:.1f}%")

            if stats.get("disk_percent", 0) >= self.disk_critical:
                status = HealthStatus.CRITICAL
                messages.append(f"Disk usage critical: {stats['disk_percent']:.1f}%")
            elif stats.get("disk_percent", 0) >= self.disk_warning:
                if status != HealthStatus.CRITICAL:
                    status = HealthStatus.WARNING
                messages.append(f"Disk usage high: {stats['disk_percent']:.1f}%")

            message = ", ".join(messages) if messages else "Resource usage normal"

            return HealthCheckResult(
                name="Resources",
                status=status,
                message=message,
                value=stats,
            )

        except Exception as e:
            return HealthCheckResult(
                name="Resources",
                status=HealthStatus.UNKNOWN,
                message=f"Resource check error: {e}",
            )

    def _check_log_errors(self, instance: Instance) -> HealthCheckResult:
        """Check for errors in logs."""
        try:
            logs = instance.get_logs(follow=False, tail=100)

            error_count = logs.lower().count("error")
            warning_count = logs.lower().count("warning")

            if error_count > 10:
                return HealthCheckResult(
                    name="Log Errors",
                    status=HealthStatus.CRITICAL,
                    message=f"Found {error_count} errors in recent logs",
                    value={"errors": error_count, "warnings": warning_count},
                )
            elif warning_count > 20:
                return HealthCheckResult(
                    name="Log Errors",
                    status=HealthStatus.WARNING,
                    message=f"Found {warning_count} warnings in recent logs",
                    value={"errors": error_count, "warnings": warning_count},
                )
            else:
                return HealthCheckResult(
                    name="Log Errors",
                    status=HealthStatus.HEALTHY,
                    message=f"Log levels normal ({error_count} errors, {warning_count} warnings)",
                    value={"errors": error_count, "warnings": warning_count},
                )
        except Exception as e:
            return HealthCheckResult(
                name="Log Errors",
                status=HealthStatus.UNKNOWN,
                message=f"Log check error: {e}",
            )

    def _get_docker_stats(self, instance: Instance) -> dict[str, Any]:
        """Get Docker container resource usage."""
        try:
            import docker

            client = docker.from_env()
            container = client.containers.get(f"odoo-{instance.config.name}")

            stats = container.stats(stream=False)

            # CPU calculation
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"][
                "cpu_usage"
            ]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"][
                "system_cpu_usage"
            ]
            online_cpus = stats["cpu_stats"].get("online_cpus", 1)
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0 if system_delta > 0 else 0.0

            # Memory calculation
            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_limit = stats["memory_stats"].get("limit", 1)
            memory_percent = (memory_usage / memory_limit) * 100.0 if memory_limit > 0 else 0.0

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent

            return {
                "cpu": cpu_percent,
                "memory_mb": memory_usage // (1024 * 1024),
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
            }

        except Exception as e:
            # Fallback to system stats
            return self._get_process_stats(instance)

    def _get_process_stats(self, instance: Instance) -> dict[str, Any]:
        """Get system process resource usage."""
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "cpu": cpu,
            "memory_mb": memory.used // (1024 * 1024),
            "memory_percent": memory.percent,
            "disk_percent": disk.percent,
        }


class AutoRestart:
    """Automatic restart on failure."""

    def __init__(self, max_restarts: int = 3, restart_window: int = 300):
        """Initialize auto-restart.

        Args:
            max_restarts: Maximum restarts within window.
            restart_window: Time window in seconds.
        """
        self.max_restarts = max_restarts
        self.restart_window = restart_window
        self.restart_history: dict[str, list[datetime]] = {}

    def should_restart(self, instance_name: str) -> bool:
        """Check if instance should be auto-restarted.

        Args:
            instance_name: Instance name.

        Returns:
            True if restart is allowed.
        """
        now = datetime.now()

        if instance_name not in self.restart_history:
            self.restart_history[instance_name] = []

        # Clean old restarts outside window
        self.restart_history[instance_name] = [
            t
            for t in self.restart_history[instance_name]
            if (now - t).total_seconds() < self.restart_window
        ]

        # Check if under limit
        return len(self.restart_history[instance_name]) < self.max_restarts

    def record_restart(self, instance_name: str) -> None:
        """Record a restart event.

        Args:
            instance_name: Instance name.
        """
        if instance_name not in self.restart_history:
            self.restart_history[instance_name] = []

        self.restart_history[instance_name].append(datetime.now())
        info(f"Recorded restart for {instance_name}")

    def get_restart_count(self, instance_name: str) -> int:
        """Get restart count within window.

        Args:
            instance_name: Instance name.

        Returns:
            Number of restarts in the window.
        """
        if instance_name not in self.restart_history:
            return 0

        now = datetime.now()
        return len(
            [
                t
                for t in self.restart_history[instance_name]
                if (now - t).total_seconds() < self.restart_window
            ]
        )
