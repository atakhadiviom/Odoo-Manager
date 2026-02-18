"""
Task scheduler for Odoo Manager using APScheduler.
"""

import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from odoo_manager.constants import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_LOG_DIR,
    SCHEDULER_LOG_FILE,
    SCHEDULER_PID_FILE,
)
from odoo_manager.exceptions import SchedulerError
from odoo_manager.utils.output import info, error, warn, success


class ScheduledTask:
    """A scheduled task definition."""

    def __init__(
        self,
        task_id: str,
        func: Callable,
        cron_expression: str,
        name: Optional[str] = None,
        kwargs: Optional[dict[str, Any]] = None,
    ):
        self.task_id = task_id
        self.func = func
        self.cron_expression = cron_expression
        self.name = name or task_id
        self.kwargs = kwargs or {}


class SchedulerManager:
    """Manages scheduled tasks for Odoo Manager."""

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        log_dir: Optional[Path] = None,
    ):
        """Initialize the scheduler manager.

        Args:
            config_dir: Configuration directory.
            log_dir: Log directory.
        """
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.log_dir = log_dir or DEFAULT_LOG_DIR
        self.pid_file = SCHEDULER_PID_FILE
        self.log_file = SCHEDULER_LOG_FILE

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Set up logging
        self._setup_logging()

        # Create scheduler
        self.scheduler = BackgroundScheduler(
            logger=self.logger,
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 3600,
            },
        )

        # Add event listeners
        self.scheduler.add_listener(
            self._job_executed, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

        self.tasks: dict[str, ScheduledTask] = {}

    def _setup_logging(self) -> None:
        """Set up logging for the scheduler."""
        self.logger = logging.getLogger("odoo-manager.scheduler")
        self.logger.setLevel(logging.INFO)

        # File handler
        handler = logging.FileHandler(self.log_file)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _job_executed(self, event) -> None:
        """Handle job execution events."""
        if event.exception:
            self.logger.error(
                f"Job {event.job_id} failed: {event.exception}",
                exc_info=event.exception,
            )
        else:
            self.logger.info(f"Job {event.job_id} completed successfully")

    def add_task(
        self,
        task_id: str,
        func: Callable,
        cron_expression: str,
        name: Optional[str] = None,
        kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a scheduled task.

        Args:
            task_id: Unique identifier for the task.
            func: Function to execute.
            cron_expression: Cron expression (e.g., "0 2 * * *").
            name: Human-readable name.
            kwargs: Keyword arguments to pass to the function.
        """
        task = ScheduledTask(task_id, func, cron_expression, name, kwargs)
        self.tasks[task_id] = task

        # Parse cron expression
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        minute, hour, day, month, day_of_week = parts

        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        )

        self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=task_id,
            name=name or task_id,
            kwargs=kwargs or {},
            replace_existing=True,
        )

        self.logger.info(f"Added scheduled task: {task_id} ({cron_expression})")

    def remove_task(self, task_id: str) -> None:
        """Remove a scheduled task.

        Args:
            task_id: Task identifier to remove.
        """
        if task_id in self.tasks:
            del self.tasks[task_id]

        try:
            self.scheduler.remove_job(task_id)
            self.logger.info(f"Removed scheduled task: {task_id}")
        except Exception as e:
            raise SchedulerError(f"Failed to remove task {task_id}: {e}")

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all scheduled tasks.

        Returns:
            List of task information dictionaries.
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                }
            )
        return jobs

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID.

        Args:
            task_id: Task identifier.

        Returns:
            ScheduledTask or None if not found.
        """
        return self.tasks.get(task_id)

    def start(self) -> None:
        """Start the scheduler daemon."""
        # Check if already running
        if self.is_running():
            raise SchedulerError("Scheduler is already running")

        # Write PID file
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

        # Start scheduler
        self.scheduler.start()
        self.logger.info("Scheduler started")

        info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler daemon."""
        if not self.scheduler.running:
            raise SchedulerError("Scheduler is not running")

        self.scheduler.shutdown(wait=True)
        self.logger.info("Scheduler stopped")

        # Remove PID file
        if self.pid_file.exists():
            self.pid_file.unlink()

        success("Scheduler stopped")

    def is_running(self) -> bool:
        """Check if the scheduler is running.

        Returns:
            True if scheduler is running.
        """
        if not self.pid_file.exists():
            return False

        try:
            with open(self.pid_file, "r") as f:
                pid = int(f.read().strip())

            # Check if process exists
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                # Process not running, clean up stale PID file
                self.pid_file.unlink()
                return False
        except (ValueError, IOError, OSError):
            return False

    def run_task_now(self, task_id: str) -> None:
        """Run a task immediately.

        Args:
            task_id: Task identifier.
        """
        if task_id not in self.tasks:
            raise SchedulerError(f"Task not found: {task_id}")

        task = self.tasks[task_id]
        self.logger.info(f"Running task now: {task_id}")

        try:
            if task.kwargs:
                task.func(**task.kwargs)
            else:
                task.func()
        except Exception as e:
            self.logger.error(f"Task {task_id} failed: {e}", exc_info=e)
            raise


def create_backup_task(
    backup_func: Callable,
    environment: str,
    cron_expression: str = "0 2 * * *",
) -> ScheduledTask:
    """Create a scheduled backup task.

    Args:
        backup_func: Function to perform the backup.
        environment: Environment name.
        cron_expression: Cron expression for scheduling.

    Returns:
        ScheduledTask for backups.
    """
    task_id = f"backup-{environment}"

    def wrapper():
        try:
            backup_func(environment)
        except Exception as e:
            logging.getLogger("odoo-manager.scheduler").error(
                f"Backup failed for {environment}: {e}",
                exc_info=e,
            )
            raise

    return ScheduledTask(
        task_id=task_id,
        func=wrapper,
        cron_expression=cron_expression,
        name=f"Backup {environment}",
    )


def create_health_check_task(
    check_func: Callable,
    instance_name: str,
    cron_expression: str = "*/5 * * * *",
) -> ScheduledTask:
    """Create a scheduled health check task.

    Args:
        check_func: Function to perform health check.
        instance_name: Instance name to check.
        cron_expression: Cron expression for scheduling.

    Returns:
        ScheduledTask for health checks.
    """
    task_id = f"health-check-{instance_name}"

    def wrapper():
        try:
            check_func(instance_name)
        except Exception as e:
            logging.getLogger("odoo-manager.scheduler").error(
                f"Health check failed for {instance_name}: {e}",
                exc_info=e,
            )
            raise

    return ScheduledTask(
        task_id=task_id,
        func=wrapper,
        cron_expression=cron_expression,
        name=f"Health check {instance_name}",
    )


# For standalone scheduler daemon
def run_scheduler_daemon() -> None:
    """Run the scheduler as a standalone daemon."""

    def signal_handler(signum, frame):
        info("Shutting down scheduler...")
        scheduler = SchedulerManager()
        if scheduler.is_running():
            scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    scheduler = SchedulerManager()
    scheduler.start()

    info("Scheduler daemon running. Press Ctrl+C to stop.")

    try:
        # Keep the process running
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    run_scheduler_daemon()
