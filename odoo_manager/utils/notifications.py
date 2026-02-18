"""
Notification utilities for Odoo Manager.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from odoo_manager.utils.output import info, warn, error


@dataclass
class NotificationMessage:
    """A notification message."""

    title: str
    message: str
    level: str = "info"  # info, warning, error, success
    details: Optional[dict[str, Any]] = None


class NotificationSender:
    """Base class for sending notifications."""

    def send(self, notification: NotificationMessage) -> bool:
        """Send a notification.

        Args:
            notification: Notification to send.

        Returns:
            True if sent successfully.
        """
        raise NotImplementedError


class WebhookNotificationSender(NotificationSender):
    """Send notifications via HTTP webhook."""

    def __init__(self, url: str, timeout: float = 5.0):
        """Initialize webhook sender.

        Args:
            url: Webhook URL.
            timeout: Request timeout in seconds.
        """
        self.url = url
        self.timeout = timeout

    def send(self, notification: NotificationMessage) -> bool:
        """Send notification via webhook."""
        try:
            payload = {
                "title": notification.title,
                "message": notification.message,
                "level": notification.level,
            }

            if notification.details:
                payload["details"] = notification.details

            response = httpx.post(self.url, json=payload, timeout=self.timeout)
            response.raise_for_status()

            return True

        except Exception as e:
            logging.getLogger("odoo-manager.notifications").warning(
                f"Failed to send webhook notification: {e}"
            )
            return False


class SlackNotificationSender(NotificationSender):
    """Send notifications to Slack."""

    def __init__(self, webhook_url: str, timeout: float = 5.0):
        """Initialize Slack sender.

        Args:
            webhook_url: Slack webhook URL.
            timeout: Request timeout in seconds.
        """
        self.webhook_url = webhook_url
        self.timeout = timeout

    def send(self, notification: NotificationMessage) -> bool:
        """Send notification to Slack."""
        try:
            color = {
                "info": "#36a64f",
                "success": "#36a64f",
                "warning": "#ff9800",
                "error": "#dc3545",
            }.get(notification.level, "#36a64f")

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": notification.title,
                        "text": notification.message,
                        "footer": "Odoo Manager",
                    }
                ]
            }

            response = httpx.post(self.webhook_url, json=payload, timeout=self.timeout)
            response.raise_for_status()

            return True

        except Exception as e:
            logging.getLogger("odoo-manager.notifications").warning(
                f"Failed to send Slack notification: {e}"
            )
            return False


class EmailNotificationSender(NotificationSender):
    """Send notifications via email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_address: str,
        to_addresses: list[str],
    ):
        """Initialize email sender.

        Args:
            smtp_host: SMTP server host.
            smtp_port: SMTP server port.
            username: SMTP username.
            password: SMTP password.
            from_address: From email address.
            to_addresses: List of recipient addresses.
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.to_addresses = to_addresses

    def send(self, notification: NotificationMessage) -> bool:
        """Send notification via email."""
        try:
            import smtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["Subject"] = notification.title
            msg["From"] = self.from_address
            msg["To"] = ", ".join(self.to_addresses)

            body = notification.message
            if notification.details:
                body += "\n\nDetails:\n"
                for key, value in notification.details.items():
                    body += f"  {key}: {value}\n"

            msg.set_content(body)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            return True

        except Exception as e:
            logging.getLogger("odoo-manager.notifications").warning(
                f"Failed to send email notification: {e}"
            )
            return False


class NotificationManager:
    """Manages notification sending."""

    def __init__(self):
        """Initialize notification manager."""
        self.senders: list[NotificationSender] = []
        self._load_senders()

    def _load_senders(self) -> None:
        """Load notification senders from environment variables."""
        # Webhook URL
        webhook_url = os.getenv("ODOO_MANAGER_WEBHOOK_URL")
        if webhook_url:
            self.senders.append(WebhookNotificationSender(webhook_url))

        # Slack webhook
        slack_url = os.getenv("ODOO_MANAGER_SLACK_WEBHOOK_URL")
        if slack_url:
            self.senders.append(SlackNotificationSender(slack_url))

        # Email configuration (requires all fields)
        smtp_host = os.getenv("ODOO_MANAGER_SMTP_HOST")
        smtp_port = os.getenv("ODOO_MANAGER_SMTP_PORT")
        smtp_user = os.getenv("ODOO_MANAGER_SMTP_USER")
        smtp_password = os.getenv("ODOO_MANAGER_SMTP_PASSWORD")
        email_from = os.getenv("ODOO_MANAGER_EMAIL_FROM")
        email_to = os.getenv("ODOO_MANAGER_EMAIL_TO")

        if all([smtp_host, smtp_port, smtp_user, smtp_password, email_from, email_to]):
            self.senders.append(
                EmailNotificationSender(
                    smtp_host=smtp_host,
                    smtp_port=int(smtp_port),
                    username=smtp_user,
                    password=smtp_password,
                    from_address=email_from,
                    to_addresses=email_to.split(","),
                )
            )

    def send(self, notification: NotificationMessage) -> int:
        """Send notification to all configured senders.

        Args:
            notification: Notification to send.

        Returns:
            Number of senders that succeeded.
        """
        if not self.senders:
            logging.getLogger("odoo-manager.notifications").debug(
                "No notification senders configured"
            )
            return 0

        success_count = 0
        for sender in self.senders:
            if sender.send(notification):
                success_count += 1

        return success_count

    def info(self, title: str, message: str, details: Optional[dict] = None) -> int:
        """Send info notification."""
        return self.send(
            NotificationMessage(title=title, message=message, level="info", details=details)
        )

    def success(self, title: str, message: str, details: Optional[dict] = None) -> int:
        """Send success notification."""
        return self.send(
            NotificationMessage(title=title, message=message, level="success", details=details)
        )

    def warning(self, title: str, message: str, details: Optional[dict] = None) -> int:
        """Send warning notification."""
        return self.send(
            NotificationMessage(title=title, message=message, level="warning", details=details)
        )

    def error(self, title: str, message: str, details: Optional[dict] = None) -> int:
        """Send error notification."""
        return self.send(
            NotificationMessage(title=title, message=message, level="error", details=details)
        )


# Global notification manager instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get the global notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def send_alert(title: str, message: str = "", details: Optional[dict] = None) -> int:
    """Send an alert notification.

    Args:
        title: Alert title.
        message: Alert message.
        details: Optional details dict.

    Returns:
        Number of senders that succeeded.
    """
    return get_notification_manager().error(title, message or "", details)


def send_deployment_notification(
    environment: str,
    branch: str,
    status: str,
    commit: str = "",
) -> int:
    """Send a deployment notification.

    Args:
        environment: Environment name.
        branch: Git branch.
        status: Deployment status (success, failure, rollback).
        commit: Commit hash.

    Returns:
        Number of senders that succeeded.
    """
    level = "success" if status == "success" else "error"

    return get_notification_manager().send(
        NotificationMessage(
            title=f"Deployment {status}",
            message=f"Deployed {branch} to {environment}",
            level=level,
            details={"environment": environment, "branch": branch, "commit": commit},
        )
    )
