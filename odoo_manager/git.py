"""
Git integration for Odoo instances.

Handles cloning repositories, pulling changes, and auto-deployment.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from odoo_manager.instance import Instance


class GitManager:
    """Manage Git repositories for Odoo instances."""

    def __init__(self, instance: Instance):
        self.instance = instance
        self.repo_dir = instance.addons_dir

    def clone_repo(self, repo_url: str, branch: Optional[str] = None) -> None:
        """Clone a Git repository to the instance addons directory.

        Args:
            repo_url: Git repository URL (HTTPS or SSH)
            branch: Optional branch name to clone
        """
        # Clone to a subdirectory to keep structure clean
        repo_name = self._get_repo_name(repo_url)
        target_dir = self.repo_dir / repo_name

        if target_dir.exists():
            raise RuntimeError(f"Directory {target_dir} already exists")

        cmd = ["git", "clone"]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([repo_url, str(target_dir)])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone repository: {result.stderr}")

    def pull_latest(self) -> str:
        """Pull latest changes from the repository.

        Returns:
            Commit hash of the latest pull
        """
        # Find git directories in addons
        git_dirs = list(self.repo_dir.rglob(".git"))
        if not git_dirs:
            raise RuntimeError("No Git repository found in addons directory")

        results = []
        for git_dir in git_dirs:
            repo_path = git_dir.parent
            os.chdir(repo_path)

            # Fetch and pull
            subprocess.run(["git", "fetch"], capture_output=True, text=True)
            result = subprocess.run(
                ["git", "pull"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"Failed to pull in {repo_path}: {result.stderr}")

            # Get current commit
            commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True
            )
            results.append(f"{repo_path.name}: {commit_result.stdout.strip()[:8]}")

        return "\n".join(results)

    def get_current_commit(self) -> str:
        """Get the current Git commit hash."""
        git_dirs = list(self.repo_dir.rglob(".git"))
        if not git_dirs:
            return "no-repo"

        repo_path = git_dirs[0].parent
        os.chdir(repo_path)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()

    def get_current_branch(self) -> str:
        """Get the current Git branch name."""
        git_dirs = list(self.repo_dir.rglob(".git"))
        if not git_dirs:
            return "no-repo"

        repo_path = git_dirs[0].parent
        os.chdir(repo_path)

        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()

    def list_modules(self) -> list[str]:
        """List Odoo modules in the repository.

        Scans for directories containing __manifest__.py or __openerp__.py files.
        """
        modules = []
        for manifest_dir in self.repo_dir.rglob("__manifest__.py"):
            module_dir = manifest_dir.parent
            if module_dir.parent != self.repo_dir:  # Not a direct module
                modules.append(module_dir.name)
        return sorted(set(modules))

    def _get_repo_name(self, repo_url: str) -> str:
        """Extract repository name from URL."""
        # Remove .git suffix if present
        url = repo_url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        return url.split("/")[-1]


class AutoDeployer:
    """Handle automatic deployment from Git webhooks."""

    def __init__(self, instances_root: Path = Path.home() / "odoo-manager" / "data"):
        self.instances_root = instances_root

    def handle_webhook(self, repo_url: str, branch: str, commit: str) -> dict[str, str]:
        """Handle a Git webhook payload.

        Args:
            repo_url: Repository URL
            branch: Branch name that was pushed
            commit: Commit hash

        Returns:
            Dictionary with deployment results per instance
        """
        from odoo_manager.instance import InstanceManager

        manager = InstanceManager()
        results = {}

        for instance in manager.list_instances():
            if instance.config.git_repo != repo_url:
                continue

            # Check if this instance should deploy from this branch
            instance_branch = instance.config.git_branch or "main"
            if branch != instance_branch:
                continue

            git_mgr = GitManager(instance)

            try:
                # Pull latest changes
                git_mgr.pull_latest()

                # Restart the instance
                instance.restart()

                results[instance.config.name] = "deployed"
            except Exception as e:
                results[instance.config.name] = f"failed: {e}"

        return results

    def start_webhook_server(self, port: int = 8080) -> None:
        """Start a simple Flask webhook server.

        This runs a blocking server that listens for GitHub/GitLab webhooks.
        """
        try:
            from flask import Flask, request, jsonify
        except ImportError:
            raise RuntimeError("Flask is required for webhook server. Install with: pip install flask")

        app = Flask(__name__)

        @app.route("/webhook/<instance_name>", methods=["POST"])
        def webhook(instance_name: str):
            """Handle webhook for a specific instance."""
            data = request.get_json()

            # GitHub webhook
            if "ref" in data:
                branch = data["ref"].replace("refs/heads/", "")
                repo_url = data.get("repository", {}).get("clone_url", "")
                commit = data.get("after", "")

            # GitLab webhook
            elif "ref" in data.get("object_kind", ""):
                branch = data.get("ref", "")
                repo_url = data.get("project", {}).get("git_http_url", "")
                commit = data.get("checkout_sha", "")

            else:
                return jsonify({"error": "Unsupported webhook format"}), 400

            from odoo_manager.instance import InstanceManager
            manager = InstanceManager()
            instance = manager.get_instance(instance_name)

            if not instance:
                return jsonify({"error": "Instance not found"}), 404

            git_mgr = GitManager(instance)
            try:
                git_mgr.pull_latest()
                instance.restart()
                return jsonify({"status": "deployed", "commit": commit})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @app.route("/health", methods=["GET"])
        def health():
            """Health check endpoint."""
            return jsonify({"status": "healthy"})

        app.run(host="0.0.0.0", port=port)
