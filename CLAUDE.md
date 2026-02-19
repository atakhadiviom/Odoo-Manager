# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Installation & Development

```bash
# Install in development mode
pip install -e .

# Run with interactive menu (no arguments)
odoo-manager

# Or use the shorter alias
om

# Install development dependencies
pip install -e ".[dev]"
```

## CLI Structure

This is a Click-based CLI tool. The main entry point is `odoo_manager/cli.py:main()`. When run without arguments, it displays an interactive menu.

Command groups are organized under `odoo_manager/commands/`:
- `instance` - Create, start, stop, list, remove instances
- `db` - Database operations (create, drop, backup, restore, duplicate)
- `module` - Module management (install, uninstall, update, list)
- `backup` - Backup management with retention policies
- `logs` - View logs with follow mode
- `shell` - Odoo Python shell access
- `git` - Git repository management for deployments
- `env` - Multi-environment management (dev/staging/production)
- `deploy` - CI/CD pipeline with validation and rollbacks
- `monitor` - Health monitoring with resource tracking
- `scheduler` - Scheduled tasks management
- `ssh` - SSH access to instances
- `user` - User management with roles
- `ssl` - SSL/TLS certificate management
- `tui` - Terminal UI (Textual-based)

## Architecture

### Core Pattern: Deployer Strategy

The codebase uses a strategy pattern for deployment. The `Instance` class (`odoo_manager/core/instance.py`) delegates deployment-specific operations to a deployer:

- `BaseDeployer` (`odoo_manager/deployers/base.py`) - Abstract base defining the contract
- `DockerDeployer` - Docker Compose-based deployment
- `SourceDeployer` - Traditional Python/systemd deployment

Each deployer implements: `create()`, `start()`, `stop()`, `restart()`, `status()`, `is_running()`, `remove()`, `exec_command()`, `get_logs()`

### Configuration

Configuration uses Pydantic models for validation, stored in YAML:
- `Config` - Main configuration loaded from `~/.config/odoo-manager/config.yaml`
- `InstancesFile` - Separate manager for `~/.config/odoo-manager/instances.yaml`
- `InstanceConfig` - Per-instance configuration
- `EnvironmentConfig` - Environment tier configuration (dev/staging/production)

Default paths are defined in `odoo_manager/constants.py`.

### Instance Management

`InstanceManager` handles multiple instances. Key flow:
1. `create_instance()` - Creates `InstanceConfig`, saves to instances.yaml, creates deployment
2. `get_instance()` - Loads config by name, returns `Instance` wrapper
3. `list_instances()` - Returns all configured instances

### Manager Classes

Core managers in `odoo_manager/core/`:
- `InstanceManager` - Instance lifecycle
- `DatabaseManager` - PostgreSQL operations
- `ModuleManager` - Odoo module operations
- `BackupManager` - Backup/restore with retention
- `HealthMonitor` - Resource usage tracking
- `GitManager` - Git operations for repos

## Code Style

- Line length: 100 characters
- Python 3.11+
- Type hints with `X | Y` syntax (not `Optional[X]` when `X | None` is clearer)
- Use `rich.console.Console` for formatted output
- Custom exceptions in `odoo_manager/exceptions.py`

## Key Constants

From `odoo_manager/constants.py`:
- Deployment types: `DEPLOYMENT_DOCKER`, `DEPLOYMENT_SOURCE`
- Instance states: `STATE_RUNNING`, `STATE_STOPPED`, `STATE_ERROR`, `STATE_UNKNOWN`
- Editions: `EDITION_COMMUNITY`, `EDITION_ENTERPRISE`
- Environment tiers: `ENV_TIER_DEV`, `ENV_TIER_STAGING`, `ENV_TIER_PRODUCTION`

## Terminal UI

The TUI (`odoo_manager/tui/app.py`) uses Textual framework. It provides:
- Instance list with status indicators
- Resource monitoring (CPU/memory)
- Action buttons for start/stop/restart
- Log viewer with auto-scroll

Launch with `odoo-manager ui` or select [T] from the menu.

## Click Decorator Pattern

Commands are defined with `@click.group()` and `@click.command()`. Important: when using `@click.pass_context`, the context object contains:
- `ctx.obj["config"]` - Path to config file
- `ctx.obj["verbose"]` - Verbose flag
- `ctx.obj["json"]` - JSON output flag

## Common Operations

```bash
# Initialize config first time
odoo-manager config init

# Create and start an instance
odoo-manager instance create myinstance --version 17.0 --port 8069
odoo-manager instance start myinstance

# Open Odoo shell (requires running instance)
odoo-manager shell myinstance

# View logs
odoo-manager logs show myinstance --follow
```
