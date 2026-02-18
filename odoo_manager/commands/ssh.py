"""
SSH commands for Odoo Manager CLI.
"""

from pathlib import Path

import click

from odoo_manager.core.ssh import ContainerSSH, SSHKeyManager, SSHManager
from odoo_manager.core.instance import InstanceManager
from odoo_manager.utils.output import console, success, error, info


@click.group(name="ssh")
def ssh_cli():
    """SSH access to Odoo instances."""
    pass


@ssh_cli.command(name="shell")
@click.argument("instance")
@click.pass_context
def ssh_shell(ctx, instance):
    """Open an interactive shell in the instance.

    Example: odoo-manager ssh shell production
    """
    try:
        manager = InstanceManager()
        inst = manager.get_instance(instance)
        data_dir = manager.config.settings.data_dir

        ContainerSSH.get_shell(inst.config, data_dir)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssh_cli.command(name="exec")
@click.argument("instance")
@click.argument("command", nargs=-1)
@click.option("--capture", "-c", is_flag=True, help="Capture and display output")
@click.pass_context
def ssh_exec(ctx, instance, command, capture):
    """Execute a command in the instance.

    Example: odoo-manager ssh exec production -- python --version
    """
    if not command:
        error("No command specified")
        ctx.exit(1)

    try:
        manager = InstanceManager()
        inst = manager.get_instance(instance)
        data_dir = manager.config.settings.data_dir

        exit_code, output = ContainerSSH.exec_command(inst.config, list(command), data_dir)

        if capture:
            console.print(output)

        if exit_code != 0:
            error(f"Command failed with exit code {exit_code}")
            ctx.exit(exit_code)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssh_cli.command(name="odoo-shell")
@click.argument("instance")
@click.option("--command", "-c", help="Python command to execute in Odoo shell")
@click.pass_context
def ssh_odoo_shell(ctx, instance, command):
    """Open an Odoo shell (python with odoo environment).

    Example: odoo-manager ssh odoo-shell production
    """
    try:
        manager = InstanceManager()
        inst = manager.get_instance(instance)
        data_dir = manager.config.settings.data_dir

        if command:
            # Execute command and exit
            exit_code, output = ContainerSSH.exec_command(
                inst.config, ["shell", "--command", command], data_dir
            )
            console.print(output)
            if exit_code != 0:
                ctx.exit(exit_code)
        else:
            # Interactive shell
            ContainerSSH.get_shell(inst.config, data_dir)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssh_cli.command(name="keys")
@click.option("--list", "-l", "list_keys", is_flag=True, help="List all SSH keys")
@click.option("--generate", "-g", help="Generate a new SSH key with the given name")
@click.option("--remove", "-r", help="Remove an SSH key")
@click.option("--public", "-p", help="Show public key for a given key name")
@click.pass_context
def ssh_keys(ctx, list_keys, generate, remove, public):
    """Manage SSH keys.

    Example: odoo-manager ssh keys --generate mykey
    """
    try:
        key_manager = SSHKeyManager()

        if list_keys:
            keys = key_manager.list_keys()

            if not keys:
                info("No SSH keys found")
                return

            from rich.table import Table

            table = Table(title="SSH Keys")
            table.add_column("Name", style="cyan")
            table.add_column("Private Key")
            table.add_column("Public Key")

            for key in keys:
                table.add_row(
                    key["name"],
                    key["private_key"],
                    key["public_key"] or "-",
                )

            console.print(table)

        elif generate:
            private, public = key_manager.generate_key(generate)
            success(f"Generated SSH key '{generate}'")
            console.print(f"  Private: {private}")
            console.print(f"  Public: {public}")
            console.print("\n[cyan]Public key content:[/cyan]")
            console.print(key_manager.get_public_key(generate))

        elif remove:
            key_manager.remove_key(remove)
            success(f"Removed SSH key '{remove}'")

        elif public:
            pub_key = key_manager.get_public_key(public)
            if pub_key:
                console.print(pub_key)
            else:
                error(f"Public key not found for '{public}'")
                ctx.exit(1)

        else:
            # Default to list
            keys = key_manager.list_keys()

            if not keys:
                info("No SSH keys found")
                return

            from rich.table import Table

            table = Table(title="SSH Keys")
            table.add_column("Name", style="cyan")
            table.add_column("Private Key")
            table.add_column("Public Key")

            for key in keys:
                table.add_row(
                    key["name"],
                    key["private_key"],
                    key["public_key"] or "-",
                )

            console.print(table)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssh_cli.command(name="connect")
@click.option("--host", "-h", required=True, help="SSH host")
@click.option("--port", "-p", type=int, default=22, help="SSH port")
@click.option("--user", "-u", help="SSH username")
@click.option("--password", "-w", help="SSH password (not recommended)")
@click.option("--key", "-k", help="SSH private key file")
@click.option("--command", "-c", help="Command to execute (otherwise opens shell)")
@click.pass_context
def ssh_connect(ctx, host, port, user, password, key, command):
    """Connect to a remote host via SSH.

    Example: odoo-manager ssh connect --host example.com --user admin
    """
    try:
        ssh_mgr = SSHManager(host=host, port=port, username=user)
        ssh_mgr.connect(password=password, key_filename=key)

        if command:
            exit_code, stdout, stderr = ssh_mgr.execute(command)
            if stdout:
                console.print(stdout)
            if stderr:
                console.print(stderr, style="dim")
            if exit_code != 0:
                error(f"Command failed with exit code {exit_code}")
                ctx.exit(exit_code)
        else:
            info(f"Connected to {host}. Opening interactive shell...")
            ssh_mgr.get_shell()

        ssh_mgr.disconnect()

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssh_cli.command(name="scp")
@click.argument("source")
@click.argument("dest")
@click.option("--host", "-h", help="SSH host (for remote transfers)")
@click.option("--user", "-u", help="SSH username")
@click.option("--key", "-k", help="SSH private key file")
@click.pass_context
def ssh_scp(ctx, source, dest, host, user, key):
    """Copy files to/from instance or remote host.

    Example: odoo-manager ssh scp /local/file.txt instance:/remote/path/
    """
    try:
        # Parse source/dest for instance syntax
        if source.startswith("instance:") or dest.startswith("instance:"):
            # Extract instance name
            parts = source.split(":") if ":" in source else dest.split(":")
            instance_name = parts[0].replace("instance:", "")

            manager = InstanceManager()
            inst = manager.get_instance(instance_name)

            info(f"Transferring file to/from instance '{instance_name}'")
            info("Note: Container file transfer requires manual docker cp or similar")
            info(f"Use: docker cp {source} odoo-{instance_name}:/path/")

        elif host:
            # Remote SSH transfer
            ssh_mgr = SSHManager(host=host, username=user)
            ssh_mgr.connect(key_filename=key)

            if ":" in dest:
                # Upload to remote
                ssh_mgr.upload(source, dest.split(":")[1])
                success(f"Uploaded {source} to {host}:{dest}")
            else:
                # Download from remote
                ssh_mgr.download(source, dest)
                success(f"Downloaded {host}:{source} to {dest}")

            ssh_mgr.disconnect()

        else:
            error("Specify --host for remote transfers or use instance: syntax")
            ctx.exit(1)

    except Exception as e:
        error(str(e))
        ctx.exit(1)
