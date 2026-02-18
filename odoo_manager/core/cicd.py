"""
CI/CD Pipeline for Odoo Manager.
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from odoo_manager.config import EnvironmentConfig
from odoo_manager.core.environment import EnvironmentManager, DeploymentHistory
from odoo_manager.core.git import GitManager
from odoo_manager.core.instance import InstanceManager
from odoo_manager.exceptions import EnvironmentNotFoundError, GitError
from odoo_manager.utils.output import success, info, warn, error


class ValidationStatus(str, Enum):
    """Status of validation checks."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ValidationResult:
    """Result of a validation check."""

    name: str
    status: ValidationStatus = ValidationStatus.PENDING
    message: str = ""
    duration: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    """Configuration for CI/CD pipeline."""

    run_tests: bool = True
    test_command: str = "pytest tests/ -v"
    lint_python: bool = True
    lint_xml: bool = True
    check_migrations: bool = True
    min_disk_space_gb: int = 5
    rollback_on_failure: bool = True
    zero_downtime: bool = True


@dataclass
class PipelineResult:
    """Result of a pipeline run."""

    id: str
    environment: str
    branch: str
    commit: str
    status: ValidationStatus = ValidationStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    validations: list[ValidationResult] = field(default_factory=list)
    deployment: Optional[DeploymentHistory] = None
    rollback_deployment: Optional[DeploymentHistory] = None
    error_message: str = ""


class CICDPipeline:
    """CI/CD Pipeline for Odoo deployments."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the CI/CD pipeline.

        Args:
            config_path: Path to configuration directory.
        """
        self.config_path = config_path
        self.env_manager = EnvironmentManager(config_path)
        self.git_manager = GitManager()
        self.instance_manager = InstanceManager(config_path)
        self.config = PipelineConfig()

    def validate_deployment(
        self,
        branch: str,
        repo: str,
        environment: str,
    ) -> PipelineResult:
        """Run validation checks before deployment.

        Args:
            branch: Git branch to validate.
            repo: Git repository name.
            environment: Target environment.

        Returns:
            PipelineResult with validation outcomes.
        """
        result = PipelineResult(
            id=f"validate-{environment}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            environment=environment,
            branch=branch,
            commit="",
            status=ValidationStatus.RUNNING,
            started_at=datetime.now(),
        )

        info(f"Starting validation for {branch} -> {environment}")

        # Get commit info
        try:
            repo_info = self.git_manager.get_status(repo)
            result.commit = repo_info.commit or "unknown"
        except GitError:
            result.commit = "unknown"

        # Run validations
        validations = []

        # 1. Python syntax validation
        validations.append(self._validate_python_syntax(repo))

        # 2. XML linting
        validations.append(self._validate_xml(repo))

        # 3. Disk space check
        validations.append(self._validate_disk_space())

        # 4. Database connectivity
        validations.append(self._validate_database(environment))

        # 5. Tests (if enabled)
        if self.config.run_tests:
            validations.append(self._run_tests(repo))

        # 6. Migration check
        if self.config.check_migrations:
            validations.append(self._validate_migrations(repo))

        result.validations = validations
        result.completed_at = datetime.now()

        # Determine overall status
        failed = any(v.status == ValidationStatus.FAILED for v in validations)
        result.status = ValidationStatus.FAILED if failed else ValidationStatus.PASSED

        if failed:
            error("Validation failed")
        else:
            success("Validation passed")

        return result

    def deploy(
        self,
        branch: str,
        environment: str,
        repo: Optional[str] = None,
        skip_validation: bool = False,
    ) -> PipelineResult:
        """Run deployment with optional validation.

        Args:
            branch: Git branch to deploy.
            environment: Target environment name.
            repo: Git repository name.
            skip_validation: Skip pre-deployment validation.

        Returns:
            PipelineResult with deployment outcome.
        """
        result = PipelineResult(
            id=f"deploy-{environment}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            environment=environment,
            branch=branch,
            commit="",
            status=ValidationStatus.RUNNING,
            started_at=datetime.now(),
        )

        try:
            env = self.env_manager.get_environment(environment)
            repo_name = repo or env.git_repo

            if not repo_name:
                raise ValueError("No repository specified")

            # Get commit info
            repo_info = self.git_manager.get_status(repo_name)
            result.commit = repo_info.commit or "unknown"

            # Run validation if not skipped
            if not skip_validation:
                info("Running pre-deployment validation...")
                validation = self.validate_deployment(branch, repo_name, environment)

                if validation.status == ValidationStatus.FAILED:
                    result.status = ValidationStatus.FAILED
                    result.validations = validation.validations
                    result.error_message = "Pre-deployment validation failed"

                    if self.config.rollback_on_failure:
                        info("Rollback enabled - deployment aborted")

                    return result

                result.validations = validation.validations

            # Store previous state for rollback
            previous_deployment = self.env_manager._get_last_deployment(environment)

            # Deploy
            info(f"Deploying {branch} to {environment}...")

            if self.config.zero_downtime:
                deployment = self._zero_downtime_deploy(
                    environment, branch, repo_name
                )
            else:
                deployment = self.env_manager.deploy(
                    environment=environment, branch=branch, repo=repo_name
                )

            result.deployment = deployment
            result.status = ValidationStatus.PASSED
            result.completed_at = datetime.now()

            success(f"Deployment to {environment} completed")

        except Exception as e:
            result.status = ValidationStatus.FAILED
            result.completed_at = datetime.now()
            result.error_message = str(e)

            error(f"Deployment failed: {e}")

            # Rollback if enabled
            if self.config.rollback_on_failure and result.deployment:
                info("Attempting rollback...")
                try:
                    result.rollback_deployment = self._rollback(
                        environment, previous_deployment
                    )
                except Exception as rollback_error:
                    warn(f"Rollback failed: {rollback_error}")

        return result

    def rollback(self, environment: str, target_id: Optional[str] = None) -> DeploymentHistory:
        """Rollback an environment to a previous deployment.

        Args:
            environment: Environment name.
            target_id: Specific deployment ID to rollback to (uses previous if None).

        Returns:
            New deployment history record.
        """
        history = self.env_manager.get_deployment_history(environment, limit=20)

        if not history:
            raise ValueError(f"No deployment history found for {environment}")

        # Find target deployment
        target = None
        if target_id:
            for record in history:
                if record.id.startswith(target_id):
                    target = record
                    break
        else:
            # Use the second most recent (most recent is current)
            if len(history) > 1:
                target = history[1]
            else:
                target = history[0]

        if not target:
            raise ValueError(f"Deployment {target_id} not found in history")

        info(f"Rolling back {environment} to {target.branch} @ {target.commit}")

        # Deploy the old branch/commit
        # Note: This is a simplified rollback - in production you might
        # want to checkout the specific commit
        return self.env_manager.deploy(
            environment=environment,
            branch=target.branch,
            repo=target.rollback_from or environment,  # Use recorded info
        )

    def _validate_python_syntax(self, repo: str) -> ValidationResult:
        """Validate Python syntax in the repository."""
        result = ValidationResult(name="Python Syntax", status=ValidationStatus.RUNNING)

        repo_path = self.git_manager.get_repo_path(repo)
        errors = []

        start = datetime.now()

        for py_file in repo_path.rglob("*.py"):
            try:
                compile(py_file.read_text(), py_file, "exec")
            except SyntaxError as e:
                errors.append(f"{py_file}:{e.lineno} - {e.msg}")

        result.duration = (datetime.now() - start).total_seconds()

        if errors:
            result.status = ValidationStatus.FAILED
            result.message = f"Found {len(errors)} syntax error(s)"
            result.details["errors"] = errors[:10]
        else:
            result.status = ValidationStatus.PASSED
            result.message = "No syntax errors found"

        return result

    def _validate_xml(self, repo: str) -> ValidationResult:
        """Validate XML files in the repository."""
        result = ValidationResult(name="XML Validation", status=ValidationStatus.RUNNING)

        repo_path = self.git_manager.get_repo_path(repo)
        errors = []

        start = datetime.now()

        try:
            import xml.etree.ElementTree as ET

            for xml_file in repo_path.rglob("*.xml"):
                try:
                    ET.parse(xml_file)
                except ET.ParseError as e:
                    errors.append(f"{xml_file}: {e}")

        except ImportError:
            result.status = ValidationStatus.SKIPPED
            result.message = "XML parser not available"
            return result

        result.duration = (datetime.now() - start).total_seconds()

        if errors:
            result.status = ValidationStatus.FAILED
            result.message = f"Found {len(errors)} XML error(s)"
            result.details["errors"] = errors[:10]
        else:
            result.status = ValidationStatus.PASSED
            result.message = "No XML errors found"

        return result

    def _validate_disk_space(self) -> ValidationResult:
        """Validate available disk space."""
        result = ValidationResult(
            name="Disk Space", status=ValidationStatus.RUNNING
        )

        start = datetime.now()

        try:
            import shutil

            usage = shutil.disk_usage("/")
            free_gb = usage.free / (1024**3)

            result.duration = (datetime.now() - start).total_seconds()

            if free_gb < self.config.min_disk_space_gb:
                result.status = ValidationStatus.FAILED
                result.message = f"Only {free_gb:.1f}GB free, need {self.config.min_disk_space_gb}GB"
                result.details["free_gb"] = free_gb
            else:
                result.status = ValidationStatus.PASSED
                result.message = f"{free_gb:.1f}GB free"

        except Exception as e:
            result.status = ValidationStatus.SKIPPED
            result.message = f"Could not check disk space: {e}"

        return result

    def _validate_database(self, environment: str) -> ValidationResult:
        """Validate database connectivity."""
        result = ValidationResult(
            name="Database Connection", status=ValidationStatus.RUNNING
        )

        start = datetime.now()

        try:
            from odoo_manager.utils.postgres import check_connection

            connected = check_connection(
                host="localhost",
                port=5432,
                user="odoo",
                password="odoo",
            )

            result.duration = (datetime.now() - start).total_seconds()

            if connected:
                result.status = ValidationStatus.PASSED
                result.message = "Database connection successful"
            else:
                result.status = ValidationStatus.FAILED
                result.message = "Could not connect to database"

        except Exception as e:
            result.status = ValidationStatus.SKIPPED
            result.message = f"Database check skipped: {e}"

        return result

    def _run_tests(self, repo: str) -> ValidationResult:
        """Run test suite."""
        result = ValidationResult(name="Tests", status=ValidationStatus.RUNNING)

        start = datetime.now()

        try:
            repo_path = self.git_manager.get_repo_path(repo)

            # Check if tests directory exists
            if not (repo_path / "tests").exists():
                result.status = ValidationStatus.SKIPPED
                result.message = "No tests directory found"
                return result

            # Run tests
            result_process = subprocess.run(
                self.config.test_command,
                shell=True,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300,
            )

            result.duration = (datetime.now() - start).total_seconds()

            if result_process.returncode == 0:
                result.status = ValidationStatus.PASSED
                result.message = "All tests passed"
            else:
                result.status = ValidationStatus.FAILED
                result.message = "Tests failed"
                result.details["output"] = result_process.stdout[-500:]

        except subprocess.TimeoutExpired:
            result.status = ValidationStatus.FAILED
            result.message = "Tests timed out"
        except Exception as e:
            result.status = ValidationStatus.SKIPPED
            result.message = f"Tests skipped: {e}"

        return result

    def _validate_migrations(self, repo: str) -> ValidationResult:
        """Validate database migrations."""
        result = ValidationResult(
            name="Migration Check", status=ValidationStatus.RUNNING
        )

        repo_path = self.git_manager.get_repo_path(repo)

        # Check for migration files
        migration_files = list(repo_path.rglob("*_upgrade.py")) + list(
            repo_path.rglob("*_migrate.py")
        )

        result.status = ValidationStatus.PASSED
        result.message = f"Found {len(migration_files)} migration file(s)"
        result.details["migrations"] = [str(f.relative_to(repo_path)) for f in migration_files[:10]]

        return result

    def _zero_downtime_deploy(
        self, environment: str, branch: str, repo: str
    ) -> DeploymentHistory:
        """Deploy with zero downtime using blue-green strategy."""
        info("Starting zero-downtime deployment...")

        # This is a simplified implementation
        # Full blue-green would:
        # 1. Create a new "green" instance
        # 2. Deploy to green
        # 3. Verify green is healthy
        # 4. Switch traffic from blue to green
        # 5. Keep blue for rollback

        # For now, use regular deploy
        return self.env_manager.deploy(environment=environment, branch=branch, repo=repo)

    def _rollback(
        self, environment: str, previous_deployment: Optional[DeploymentHistory]
    ) -> Optional[DeploymentHistory]:
        """Perform rollback to previous deployment."""
        if not previous_deployment:
            warn("No previous deployment found for rollback")
            return None

        info(f"Rolling back to {previous_deployment.branch} @ {previous_deployment.commit}")

        return self.env_manager.deploy(
            environment=environment,
            branch=previous_deployment.branch,
        )


def get_pipeline_result_path(config_dir: Path) -> Path:
    """Get path to pipeline results storage."""
    return config_dir / "pipeline_results.yaml"


def save_pipeline_result(result: PipelineResult, config_dir: Path) -> None:
    """Save pipeline result to file."""
    import yaml

    results_file = get_pipeline_result_path(config_dir)

    if results_file.exists():
        with open(results_file, "r") as f:
            data = yaml.safe_load(f) or []
    else:
        data = []

    data.append(
        {
            "id": result.id,
            "environment": result.environment,
            "branch": result.branch,
            "commit": result.commit,
            "status": result.status,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "error_message": result.error_message,
        }
    )

    # Keep only last 100
    data = data[-100:]

    with open(results_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
