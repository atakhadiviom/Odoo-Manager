"""
SSH operations for Odoo Manager using paramiko.
"""

import os
from pathlib import Path
from typing import Any, Optional

import paramiko
from paramiko import SSHClient, AutoAddPolicy

from odoo_manager.config import InstanceConfig
from odoo_manager.constants import DEPLOYMENT_DOCKER, DEPLOYMENT_SOURCE
from odoo_manager.deployers.base import BaseDeployer
from odoo_manager.exceptions import SSHError as OdooSSHError


class SSHManager:
    """Manages SSH connections and operations."""

    def __init__(self, host: str = "localhost", port: int = 22, username: Optional[str] = None):
        """Initialize SSH manager.

        Args:
            host: SSH host.
            port: SSH port.
            username: SSH username.
        """
        self.host = host
        self.port = port
        self.username = username or os.getenv("USER", "root")
        self.client: Optional[SSHClient] = None

    def connect(
        self,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        key_string: Optional[str] = None,
    ) -> None:
        """Establish SSH connection.

        Args:
            password: SSH password (optional if using key).
            key_filename: Path to private key file.
            key_string: Private key as string.
        """
        self.client = SSHClient()
        self.client.set_missing_host_key_policy(AutoAddPolicy())

        try:
            if key_string:
                key = paramiko.RSAKey.from_private_key_file(key_string)
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    pkey=key,
                )
            elif key_filename:
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    key_filename=key_filename,
                )
            elif password:
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=password,
                )
            else:
                # Try default key locations
                default_keys = [
                    os.path.expanduser("~/.ssh/id_rsa"),
                    os.path.expanduser("~/.ssh/id_ed25519"),
                ]

                connected = False
                for key_path in default_keys:
                    if os.path.exists(key_path):
                        try:
                            self.client.connect(
                                hostname=self.host,
                                port=self.port,
                                username=self.username,
                                key_filename=key_path,
                            )
                            connected = True
                            break
                        except paramiko.AuthenticationException:
                            continue

                if not connected:
                    raise OdooSSHError(
                        "Could not authenticate. Provide password or key file."
                    )

        except paramiko.AuthenticationException as e:
            raise OdooSSHError(f"SSH authentication failed: {e}") from e
        except paramiko.SSHException as e:
            raise OdooSSHError(f"SSH connection failed: {e}") from e
        except Exception as e:
            raise OdooSSHError(f"Connection error: {e}") from e

    def disconnect(self) -> None:
        """Close SSH connection."""
        if self.client:
            self.client.close()
            self.client = None

    def execute(self, command: str, capture: bool = True) -> tuple[int, str, str]:
        """Execute a command on the remote host.

        Args:
            command: Command to execute.
            capture: Whether to capture output.

        Returns:
            Tuple of (exit_code, stdout, stderr).
        """
        if not self.client:
            raise OdooSSHError("Not connected. Call connect() first.")

        try:
            stdin, stdout, stderr = self.client.exec_command(command)

            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode("utf-8", errors="ignore")
            stderr_text = stderr.read().decode("utf-8", errors="ignore")

            return exit_code, stdout_text, stderr_text

        except paramiko.SSHException as e:
            raise OdooSSHError(f"Command execution failed: {e}") from e

    def upload(self, local_path: str | Path, remote_path: str) -> None:
        """Upload a file to the remote host.

        Args:
            local_path: Local file path.
            remote_path: Remote file path.
        """
        if not self.client:
            raise OdooSSHError("Not connected. Call connect() first.")

        sftp = self.client.open_sftp()

        try:
            sftp.put(str(local_path), remote_path)
        finally:
            sftp.close()

    def download(self, remote_path: str, local_path: str | Path) -> None:
        """Download a file from the remote host.

        Args:
            remote_path: Remote file path.
            local_path: Local file path.
        """
        if not self.client:
            raise OdooSSHError("Not connected. Call connect() first.")

        sftp = self.client.open_sftp()

        try:
            sftp.get(remote_path, str(local_path))
        finally:
            sftp.close()

    def get_shell(self) -> None:
        """Open an interactive shell."""
        if not self.client:
            raise OdooSSHError("Not connected. Call connect() first.")

        import sys

        channel = self.client.invoke_shell()

        try:
            while True:
                # Display remote output
                if channel.recv_ready():
                    sys.stdout.write(channel.recv(1024).decode("utf-8", errors="ignore"))
                    sys.stdout.flush()

                # Send local input
                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                    user_input = sys.stdin.read(1)
                    channel.send(user_input)

                if channel.exit_status_ready():
                    break

        except KeyboardInterrupt:
            channel.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class ContainerSSH:
    """SSH access to Odoo containers."""

    @staticmethod
    def get_shell(instance: InstanceConfig, data_dir: Path) -> None:
        """Open shell in an Odoo container or process.

        Args:
            instance: Instance configuration.
            data_dir: Data directory.
        """
        if instance.deployment_type == DEPLOYMENT_DOCKER:
            ContainerSSH._docker_shell(instance)
        elif instance.deployment_type == DEPLOYMENT_SOURCE:
            ContainerSSH._source_shell(instance)
        else:
            raise OdooSSHError(f"Unsupported deployment type: {instance.deployment_type}")

    @staticmethod
    def _docker_shell(instance: InstanceConfig) -> None:
        """Open shell in Docker container."""
        import subprocess

        container_name = f"odoo-{instance.name}"
        subprocess.run(
            ["docker", "exec", "-it", container_name, "/bin/bash"]
        )

    @staticmethod
    def _source_shell(instance: InstanceConfig) -> None:
        """Open shell for source deployment (using odoo shell)."""
        import subprocess

        venv_dir = Path.home() / "odoo-manager" / "data" / instance.name / "venv"
        source_dir = Path.home() / "odoo-manager" / "data" / instance.name / "src"
        config_dir = Path.home() / "odoo-manager" / "data" / instance.name / "etc"

        python_bin = venv_dir / "bin" / "python"
        odoo_bin = source_dir / "odoo-bin"
        config_file = config_dir / "odoo.conf"

        if not odoo_bin.exists():
            odoo_bin = source_dir / "odoo" / "bin" / "odoo"

        subprocess.run(
            [
                str(python_bin),
                str(odoo_bin),
                "shell",
                "-c",
                str(config_file),
            ]
        )

    @staticmethod
    def exec_command(instance: InstanceConfig, command: list[str], data_dir: Path) -> tuple[int, str]:
        """Execute command in container/source context.

        Args:
            instance: Instance configuration.
            command: Command to execute.
            data_dir: Data directory.

        Returns:
            Tuple of (exit_code, output).
        """
        if instance.deployment_type == DEPLOYMENT_DOCKER:
            return ContainerSSH._docker_exec(instance, command)
        elif instance.deployment_type == DEPLOYMENT_SOURCE:
            return ContainerSSH._source_exec(instance, data_dir, command)
        else:
            raise OdooSSHError(f"Unsupported deployment type: {instance.deployment_type}")

    @staticmethod
    def _docker_exec(instance: InstanceConfig, command: list[str]) -> tuple[int, str]:
        """Execute command in Docker container."""
        import subprocess

        container_name = f"odoo-{instance.name}"
        result = subprocess.run(
            ["docker", "exec", container_name] + command,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout

    @staticmethod
    def _source_exec(instance: InstanceConfig, data_dir: Path, command: list[str]) -> tuple[int, str]:
        """Execute command for source deployment."""
        import subprocess
        import os

        venv_dir = data_dir / instance.name / "venv"
        source_dir = data_dir / instance.name / "src"
        config_dir = data_dir / instance.name / "etc"

        python_bin = venv_dir / "bin" / "python"
        odoo_bin = source_dir / "odoo-bin"
        config_file = config_dir / "odoo.conf"

        if not odoo_bin.exists():
            odoo_bin = source_dir / "odoo" / "bin" / "odoo"

        env = os.environ.copy()
        env["PYTHONPATH"] = str(source_dir)

        result = subprocess.run(
            [str(python_bin), str(odoo_bin)] + command + ["-c", str(config_file)],
            capture_output=True,
            text=True,
            env=env,
            cwd=source_dir,
        )
        return result.returncode, result.stdout


class SSHKeyManager:
    """Manage SSH keys for Odoo Manager."""

    DEFAULT_KEY_DIR = Path.home() / ".ssh" / "odoo-manager"

    def __init__(self, key_dir: Optional[Path] = None):
        """Initialize SSH key manager.

        Args:
            key_dir: Directory to store keys.
        """
        self.key_dir = key_dir or self.DEFAULT_KEY_DIR
        self.key_dir.mkdir(parents=True, exist_ok=True)

    def generate_key(self, name: str, comment: Optional[str] = None) -> tuple[str, str]:
        """Generate a new SSH key pair.

        Args:
            name: Name for the key.
            comment: Key comment.

        Returns:
            Tuple of (private_key_path, public_key_path).
        """
        private_key_path = self.key_dir / f"{name}"
        public_key_path = self.key_dir / f"{name}.pub"

        if private_key_path.exists():
            raise OdooSSHError(f"Key '{name}' already exists")

        import subprocess

        comment_text = comment or f"odoo-manager-{name}"

        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "rsa",
                "-b",
                "4096",
                "-f",
                str(private_key_path),
                "-C",
                comment_text,
                "-N",
                "",  # No passphrase
            ],
            check=True,
            capture_output=True,
        )

        return str(private_key_path), str(public_key_path)

    def list_keys(self) -> list[dict[str, str]]:
        """List all SSH keys.

        Returns:
            List of key information dictionaries.
        """
        keys = []

        for key_file in self.key_dir.iterdir():
            if key_file.is_file() and not key_file.name.endswith(".pub"):
                pub_file = self.key_dir / f"{key_file.name}.pub"

                key_info = {
                    "name": key_file.name,
                    "private_key": str(key_file),
                    "public_key": str(pub_file) if pub_file.exists() else None,
                }

                # Read public key if exists
                if pub_file.exists():
                    key_info["public_key_content"] = pub_file.read_text().strip()

                keys.append(key_info)

        return keys

    def remove_key(self, name: str) -> None:
        """Remove an SSH key pair.

        Args:
            name: Name of the key to remove.
        """
        private_key = self.key_dir / name
        public_key = self.key_dir / f"{name}.pub"

        if private_key.exists():
            private_key.unlink()

        if public_key.exists():
            public_key.unlink()

    def get_public_key(self, name: str) -> Optional[str]:
        """Get the public key content.

        Args:
            name: Name of the key.

        Returns:
            Public key content or None.
        """
        public_key = self.key_dir / f"{name}.pub"

        if public_key.exists():
            return public_key.read_text().strip()

        return None
