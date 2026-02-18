# Odoo Manager

A local Odoo instance management tool similar to [odoo.sh](https://www.odoo.sh) for managing Odoo instances on a server.

## Features

- **Multi-instance management** - Create, start, stop, manage multiple Odoo instances
- **Database operations** - Create, backup, restore, duplicate, drop databases
- **Module management** - Install, update, uninstall, list Odoo modules
- **Log viewing** - View and filter logs with follow mode
- **Backup/restore** - Scheduled backups with retention policies
- **Configuration management** - Unified config for all instances
- **Docker deployment** - Docker-based deployment using docker-compose
- **Source deployment** - Traditional Python installation with systemd
- **Odoo shell access** - Interactive shell for debugging
- **Terminal UI (TUI)** - Panel-style interface for visual management
- **Git integration** - Clone repositories, manage branches, deploy from git
- **Multi-environment** - Dev, staging, production workflow support
- **CI/CD pipeline** - Pre-deployment validation, automated rollbacks
- **Health monitoring** - Resource usage tracking, auto-restart on failure
- **SSH access** - Remote shell and file transfer capabilities
- **SSL/TLS** - Let's Encrypt and custom certificate support

## Installation

### From source

```bash
git clone https://github.com/atakhadiviom/Odoo-Manager.git
cd odoo-manager
pip install -e .
```

### Requirements

- Python 3.11+
- Docker (for Docker deployment)

## Quick Start

1. **Initialize configuration:**
   ```bash
   odoo-manager config init
   ```

2. **Create an instance:**
   ```bash
   odoo-manager instance create myinstance --version 17.0 --port 8069
   ```

3. **Start the instance:**
   ```bash
   odoo-manager instance start myinstance
   ```

4. **Check status:**
   ```bash
   odoo-manager instance status myinstance
   ```

5. **Access Odoo:**
   Open your browser at `http://localhost:8069`

## Usage

### Instance Management

```bash
# List all instances
odoo-manager instance list

# Create a new instance
odoo-manager instance create NAME [OPTIONS]
  --version, -v     Odoo version (default: 17.0)
  --edition, -e     community or enterprise (default: community)
  --port, -p        Port to expose (default: 8069)
  --workers, -w     Number of workers (default: 4)
  --db-name, -d     Database name

# Start an instance
odoo-manager instance start NAME

# Stop an instance
odoo-manager instance stop NAME

# Restart an instance
odoo-manager instance restart NAME

# Show instance status
odoo-manager instance status NAME

# Show detailed instance info
odoo-manager instance info NAME

# Remove an instance
odoo-manager instance rm NAME
```

### Database Management

```bash
# List databases (requires --instance or uses first available)
odoo-manager db ls --instance myinstance

# Create a new database
odoo-manager db create mydb --instance myinstance

# Drop a database
odoo-manager db drop mydb --instance myinstance

# Backup a database
odoo-manager db backup mydb --instance myinstance --output mydb.dump

# Restore from backup
odoo-manager db restore mydb.dump mydb --instance myinstance

# Duplicate a database
odoo-manager db duplicate sourcedb targetdb --instance myinstance
```

### Module Management

```bash
# List modules
odoo-manager module ls --instance myinstance

# List only installed modules
odoo-manager module ls --installed --instance myinstance

# Install a module
odoo-manager module install MODULE --instance myinstance

# Uninstall a module
odoo-manager module uninstall MODULE --instance myinstance

# Update a module
odoo-manager module update MODULE --instance myinstance

# Update all modules
odoo-manager module update --all --instance myinstance

# Show module info
odoo-manager module info MODULE --instance myinstance
```

### Backup Management

```bash
# List all backups
odoo-manager backup ls

# Create a backup
odoo-manager backup create myinstance

# Restore a backup
odoo-manager backup restore backup.dump myinstance

# Delete a backup
odoo-manager backup delete backup.dump

# Cleanup old backups
odoo-manager backup cleanup myinstance --retention 30
```

### Log Viewing

```bash
# Show logs
odoo-manager logs show myinstance

# Follow logs (live)
odoo-manager logs show myinstance --follow

# Show last 500 lines
odoo-manager logs show myinstance --tail 500

# Show PostgreSQL logs
odoo-manager logs show myinstance --service postgres
```

### Shell Access

```bash
# Open Odoo shell
odoo-manager shell myinstance

# Open shell for specific database
odoo-manager shell myinstance --database mydb
```

### Terminal UI (TUI)

```bash
# Launch the panel-style terminal interface
odoo-manager ui
```

The TUI provides:
- **Dashboard** - Overview of all instances with status indicators
- **Instance Management** - Start, stop, restart with button clicks
- **Resource Monitoring** - Real-time CPU and memory usage
- **Log Viewing** - Integrated log viewer with auto-scroll
- **Action Panel** - Quick access to common operations

Keyboard shortcuts in TUI:
- `q` - Quit
- `r` - Refresh
- `s` - Start selected instance
- `t` - Stop selected instance
- `R` - Restart selected instance
- `l` - View logs
- `tab` - Navigate between panels

### Git Integration

```bash
# Clone a repository
odoo-manager git clone https://github.com/odoo/odoo.git

# List repositories
odoo-manager git ls

# Switch branches
odoo-manager git checkout odoo 17.0

# Pull latest changes
odoo-manager git pull odoo
```

### Environment Management

```bash
# List environments
odoo-manager env ls

# Create environment
odoo-manager env create dev --tier dev

# Deploy to environment
odoo-manager env deploy 17.0 --environment dev

# Promote to staging
odoo-manager env promote dev staging
```

### Configuration

```bash
# Show current configuration
odoo-manager config show

# Show configuration file path
odoo-manager config path

# Set a configuration value
odoo-manager config set --key settings.default_edition --value community
```

## Configuration

Configuration is stored in `~/.config/odoo-manager/`:

- `config.yaml` - Main configuration
- `instances.yaml` - Instance definitions

### Default Configuration

```yaml
settings:
  data_dir: ~/odoo-manager/data
  backup_dir: ~/odoo-manager/backups
  log_dir: ~/odoo-manager/logs
  default_edition: community
  default_deployment: docker
  default_odoo_version: "17.0"

postgres:
  host: localhost
  port: 5432
  user: odoo
  password: odoo
  superuser: postgres

backup:
  retention_days: 30
  compression: gzip
  format: dump
```

## Project Structure

```
odoo-manager/
├── odoo_manager/
│   ├── cli.py                 # Main CLI entry point
│   ├── config.py              # Configuration management
│   ├── constants.py           # Constants and defaults
│   ├── exceptions.py          # Custom exceptions
│   ├── core/                  # Core functionality
│   │   ├── instance.py        # Instance model and operations
│   │   ├── database.py        # Database operations
│   │   ├── module.py          # Module management
│   │   └── backup.py          # Backup/restore operations
│   ├── commands/              # Click command groups
│   │   ├── instance.py        # Instance commands
│   │   ├── db.py              # Database commands
│   │   ├── module.py          # Module commands
│   │   ├── backup.py          # Backup commands
│   │   ├── logs.py            # Log commands
│   │   ├── config.py          # Config commands
│   │   └── shell.py           # Shell command
│   ├── deployers/             # Deployment strategies
│   │   ├── base.py            # Abstract base class
│   │   └── docker.py          # Docker deployment
│   ├── utils/                 # Utility functions
│   │   ├── postgres.py        # PostgreSQL utilities
│   │   └── output.py          # Formatted output
│   └── templates/             # Configuration templates
│       ├── odoo.conf.j2
│       └── docker-compose.yml.j2
├── config/                    # Default configurations
│   ├── default.yaml
│   └── instances.yaml.example
└── pyproject.toml
```

## License

MIT License - see LICENSE file for details.
