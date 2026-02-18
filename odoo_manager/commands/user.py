"""
User commands for Odoo Manager CLI.
"""

import getpass
from pathlib import Path

import click
from rich.table import Table

from odoo_manager.core.user import UserManager, Permission
from odoo_manager.utils.output import console, success, error, info


@click.group(name="user")
def user_cli():
    """Manage users and permissions."""
    pass


@user_cli.command(name="ls")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed user information")
@click.pass_context
def user_list(ctx, verbose):
    """List all users.

    Example: odoo-manager user ls
    """
    try:
        user_mgr = UserManager()
        users = user_mgr.list_users()

        if not users:
            info("No users found")
            return

        table = Table(title="Users")
        table.add_column("Username", style="cyan")
        table.add_column("Role", style="green")
        if verbose:
            table.add_column("Instances")
            table.add_column("Environments")
            table.add_column("Permissions")

        for user in users:
            if verbose:
                table.add_row(
                    user.name,
                    user.role,
                    ", ".join(user.instances) or "-",
                    ", ".join(user.environments) or "-",
                    ", ".join(user.permissions) or "-",
                )
            else:
                table.add_row(user.name, user.role)

        console.print(table)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="add")
@click.argument("name")
@click.option("--role", "-r", type=click.Choice(["admin", "operator", "viewer"]), default="viewer", help="User role")
@click.option("--password", "-p", help="Password (auto-generated if not provided)")
@click.option("--instance", "-i", multiple=True, help="Allowed instances")
@click.option("--environment", "-e", multiple=True, help="Allowed environments")
@click.option("--permission", "-P", multiple=True, help="Additional permissions")
@click.pass_context
def user_add(ctx, name, role, password, instance, environment, permission):
    """Create a new user.

    Example: odoo-manager user add john --role operator --instance production
    """
    try:
        user_mgr = UserManager()

        # Prompt for password if not provided
        if password is None:
            password = click.prompt("Password", hide_input=True, confirmation_prompt=True)

        user = user_mgr.create_user(
            name=name,
            password=password,
            role=role,
            instances=list(instance),
            environments=list(environment),
            permissions=list(permission),
        )

        success(f"User '{name}' created with role '{role}'")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="rm")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to remove this user?")
@click.pass_context
def user_remove(ctx, name):
    """Remove a user.

    Example: odoo-manager user rm john
    """
    try:
        user_mgr = UserManager()
        user_mgr.remove_user(name)
        success(f"User '{name}' removed")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="info")
@click.argument("name")
@click.pass_context
def user_info(ctx, name):
    """Show detailed user information.

    Example: odoo-manager user info admin
    """
    try:
        user_mgr = UserManager()
        user = user_mgr.get_user(name)

        console.print(f"[bold cyan]{user.name}[/bold cyan]")
        console.print(f"Role: [green]{user.role}[/green]")
        console.print(f"Instances: {', '.join(user.instances) or 'None'}")
        console.print(f"Environments: {', '.join(user.environments) or 'None'}")
        console.print(f"Permissions: {', '.join(user.permissions) or 'None'}")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="set-role")
@click.argument("name")
@click.argument("role")
@click.pass_context
def user_set_role(ctx, name, role):
    """Set user role.

    Example: odoo-manager user set-role john operator
    """
    try:
        user_mgr = UserManager()
        user_mgr.set_role(name, role)
        success(f"User '{name}' role set to '{role}'")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="grant")
@click.argument("name")
@click.argument("permission")
@click.pass_context
def user_grant(ctx, name, permission):
    """Grant permission to user.

    Example: odoo-manager user grant john instance:create
    """
    try:
        user_mgr = UserManager()
        user_mgr.grant_permission(name, permission)
        success(f"Granted '{permission}' to '{name}'")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="revoke")
@click.argument("name")
@click.argument("permission")
@click.pass_context
def user_revoke(ctx, name, permission):
    """Revoke permission from user.

    Example: odoo-manager user revoke john instance:delete
    """
    try:
        user_mgr = UserManager()
        user_mgr.revoke_permission(name, permission)
        success(f"Revoked '{permission}' from '{name}'")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="allow-instance")
@click.argument("name")
@click.argument("instance")
@click.pass_context
def user_allow_instance(ctx, name, instance):
    """Allow user to access an instance.

    Example: odoo-manager user allow-instance john production
    """
    try:
        user_mgr = UserManager()
        user_mgr.allow_instance(name, instance)
        success(f"Allowed '{name}' to access instance '{instance}'")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="deny-instance")
@click.argument("name")
@click.argument("instance")
@click.pass_context
def user_deny_instance(ctx, name, instance):
    """Deny user access to an instance.

    Example: odoo-manager user deny-instance john production
    """
    try:
        user_mgr = UserManager()
        user_mgr.deny_instance(name, instance)
        success(f"Denied '{name}' access to instance '{instance}'")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="allow-env")
@click.argument("name")
@click.argument("environment")
@click.pass_context
def user_allow_environment(ctx, name, environment):
    """Allow user to access an environment.

    Example: odoo-manager user allow-env john staging
    """
    try:
        user_mgr = UserManager()
        user_mgr.allow_environment(name, environment)
        success(f"Allowed '{name}' to access environment '{environment}'")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="deny-env")
@click.argument("name")
@click.argument("environment")
@click.pass_context
def user_deny_environment(ctx, name, environment):
    """Deny user access to an environment.

    Example: odoo-manager user deny-env john production
    """
    try:
        user_mgr = UserManager()
        user_mgr.deny_environment(name, environment)
        success(f"Denied '{name}' access to environment '{environment}'")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="login")
@click.option("--name", "-n", prompt=True, help="Username")
@click.option("--password", "-p", hide_input=True, prompt="Password", help="Password")
@click.pass_context
def user_login(ctx, name, password):
    """Authenticate as a user (for testing).

    Example: odoo-manager user login
    """
    try:
        user_mgr = UserManager()
        session = user_mgr.authenticate(name, password)

        if session:
            success(f"Authenticated as '{name}' (role: {session.role})")
            console.print(f"Session token: {session.token}")
        else:
            error("Authentication failed")
            ctx.exit(1)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@user_cli.command(name="permissions")
@click.pass_context
def user_permissions(ctx):
    """List available permissions.

    Example: odoo-manager user permissions
    """
    try:
        table = Table(title="Available Permissions")
        table.add_column("Permission", style="cyan")
        table.add_column("Description")

        permissions = [
            (Permission.INSTANCE_READ, "View instance information"),
            (Permission.INSTANCE_CREATE, "Create new instances"),
            (Permission.INSTANCE_UPDATE, "Update instance configuration"),
            (Permission.INSTANCE_DELETE, "Delete instances"),
            (Permission.INSTANCE_START, "Start instances"),
            (Permission.INSTANCE_STOP, "Stop instances"),
            (Permission.DB_READ, "View database information"),
            (Permission.DB_CREATE, "Create databases"),
            (Permission.DB_DELETE, "Delete databases"),
            (Permission.DB_BACKUP, "Create database backups"),
            (Permission.DB_RESTORE, "Restore database backups"),
            (Permission.MODULE_READ, "View module information"),
            (Permission.MODULE_INSTALL, "Install modules"),
            (Permission.MODULE_UNINSTALL, "Uninstall modules"),
            (Permission.MODULE_UPDATE, "Update modules"),
            (Permission.ENV_READ, "View environment information"),
            (Permission.ENV_DEPLOY, "Deploy to environments"),
            (Permission.ENV_PROMOTE, "Promote between environments"),
            (Permission.BACKUP_READ, "View backup information"),
            (Permission.BACKUP_CREATE, "Create backups"),
            (Permission.BACKUP_DELETE, "Delete backups"),
            (Permission.BACKUP_SCHEDULE, "Schedule automated backups"),
            (Permission.SYSTEM_SSH, "SSH access to instances"),
            (Permission.SYSTEM_MONITOR, "View monitoring information"),
            (Permission.SYSTEM_CONFIG, "Modify system configuration"),
        ]

        for perm, desc in permissions:
            table.add_row(perm, desc)

        console.print(table)

    except Exception as e:
        error(str(e))
        ctx.exit(1)
