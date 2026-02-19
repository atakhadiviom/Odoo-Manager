"""
Docker installation and management utilities.
"""

import os
import subprocess
import shutil
from pathlib import Path


def is_docker_installed() -> bool:
    """Check if Docker is installed."""
    return shutil.which("docker") is not None


def is_docker_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_docker() -> tuple[bool, str]:
    """
    Install Docker automatically.

    Returns:
        tuple: (success, message)
    """
    if is_docker_installed():
        if is_docker_running():
            return True, "Docker is already installed and running."
        else:
            return False, "Docker is installed but not running. Start it with: sudo systemctl start docker"

    # Detect the package manager and OS
    if shutil.which("apt-get"):
        return _install_docker_debian()
    elif shutil.which("yum"):
        return _install_docker_rhel()
    elif shutil.which("dnf"):
        return _install_docker_fedora()
    else:
        return False, "Unsupported package manager. Please install Docker manually."


def _install_docker_debian() -> tuple[bool, str]:
    """Install Docker on Debian/Ubuntu systems."""
    commands = [
        # Update package index
        ["sudo", "apt-get", "update"],
        # Install prerequisites
        ["sudo", "apt-get", "install", "-y", "curl", "ca-certificates", "gnupg"],
        # Add Docker's official GPG key
        ["install", "-m", "0755", "-d", "/etc/apt/keyrings"],
        ["curl", "-fsSL", "https://download.docker.com/linux/ubuntu/gpg"],
        # Use the convenience script (most reliable)
        ["curl", "-fsSL", "https://get.docker.com", "-o", "/tmp/get-docker.sh"],
        ["sudo", "sh", "/tmp/get-docker.sh"],
    ]

    # Use the official Docker convenience script (most reliable method)
    try:
        # Download and run the Docker installation script
        subprocess.run(
            ["curl", "-fsSL", "https://get.docker.com", "-o", "/tmp/get-docker.sh"],
            check=True,
            capture_output=True
        )

        result = subprocess.run(
            ["sudo", "sh", "/tmp/get-docker.sh"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return False, f"Installation failed: {result.stderr}"

        # Add current user to docker group
        user = os.environ.get("USER", os.environ.get("USERNAME", "ubuntu"))
        subprocess.run(
            ["sudo", "usermod", "-aG", "docker", user],
            capture_output=True
        )

        # Clean up
        subprocess.run(["rm", "-f", "/tmp/get-docker.sh"], capture_output=True)

        return True, "Docker installed successfully. Please log out and log back in for group changes to take effect."

    except subprocess.CalledProcessError as e:
        return False, f"Installation failed: {e.stderr}"
    except Exception as e:
        return False, f"Installation failed: {e}"


def _install_docker_rhel() -> tuple[bool, str]:
    """Install Docker on RHEL/CentOS systems."""
    try:
        # Set up the repository
        subprocess.run(
            ["sudo", "yum", "install", "-y", "yum-utils"],
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["sudo", "yum-config-manager", "--add-repo",
             "https://download.docker.com/linux/centos/docker-ce.repo"],
            check=True,
            capture_output=True
        )
        # Install Docker
        result = subprocess.run(
            ["sudo", "yum", "install", "-y", "docker-ce", "docker-ce-cli",
             "containerd.io", "docker-buildx-plugin", "docker-compose-plugin"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return False, f"Installation failed: {result.stderr}"

        # Start and enable Docker
        subprocess.run(["sudo", "systemctl", "start", "docker"], capture_output=True)
        subprocess.run(["sudo", "systemctl", "enable", "docker"], capture_output=True)

        # Add current user to docker group
        user = os.environ.get("USER", os.environ.get("USERNAME", "centos"))
        subprocess.run(
            ["sudo", "usermod", "-aG", "docker", user],
            capture_output=True
        )

        return True, "Docker installed successfully. Please log out and log back in for group changes to take effect."

    except Exception as e:
        return False, f"Installation failed: {e}"


def _install_docker_fedora() -> tuple[bool, str]:
    """Install Docker on Fedora systems."""
    try:
        # Install Docker
        result = subprocess.run(
            ["sudo", "dnf", "install", "-y", "docker-ce", "docker-ce-cli",
             "containerd.io", "docker-buildx-plugin", "docker-compose-plugin"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return False, f"Installation failed: {result.stderr}"

        # Start and enable Docker
        subprocess.run(["sudo", "systemctl", "start", "docker"], capture_output=True)
        subprocess.run(["sudo", "systemctl", "enable", "docker"], capture_output=True)

        # Add current user to docker group
        user = os.environ.get("USER", os.environ.get("USERNAME", "fedora"))
        subprocess.run(
            ["sudo", "usermod", "-aG", "docker", user],
            capture_output=True
        )

        return True, "Docker installed successfully. Please log out and log back in for group changes to take effect."

    except Exception as e:
        return False, f"Installation failed: {e}"


def ensure_docker(verbose: bool = True) -> tuple[bool, str]:
    """
    Ensure Docker is installed and running. Install if needed.

    Args:
        verbose: Print progress messages

    Returns:
        tuple: (success, message)
    """
    if is_docker_installed():
        if is_docker_running():
            return True, "Docker is ready."
        else:
            # Try to start Docker
            try:
                subprocess.run(
                    ["sudo", "systemctl", "start", "docker"],
                    check=True,
                    capture_output=True
                )
                return True, "Docker started successfully."
            except Exception as e:
                return False, f"Docker is installed but not running. Failed to start: {e}"

    # Docker not installed, install it
    if verbose:
        print("Docker is not installed. Installing Docker now...")

    success, message = install_docker()

    if success and verbose:
        # Give Docker a moment to start
        import time
        time.sleep(2)

    return success, message
