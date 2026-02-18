"""
SSL commands for Odoo Manager CLI.
"""

from pathlib import Path

import click
from rich.table import Table

from odoo_manager.core.ssl import SSLManager, NginxConfig, CertificateType
from odoo_manager.core.instance import InstanceManager
from odoo_manager.utils.output import console, success, error, info, warn


@click.group(name="ssl")
def ssl_cli():
    """Manage SSL/TLS certificates."""
    pass


@ssl_cli.command(name="generate")
@click.argument("domain")
@click.option("--validity", "-v", type=int, default=365, help="Validity in days")
@click.pass_context
def ssl_generate(ctx, domain, validity):
    """Generate a self-signed certificate.

    Example: odoo-manager ssl generate localhost.localdomain --validity 365
    """
    try:
        ssl_mgr = SSLManager()
        cert_info = ssl_mgr.generate_self_signed(domain, validity)

        success(f"Generated self-signed certificate for '{domain}'")
        console.print(f"  Certificate: {cert_info.cert_path}")
        console.print(f"  Private key: {cert_info.key_path}")
        console.print(f"  Valid until: {cert_info.valid_until.strftime('%Y-%m-%d')}")
        console.print()
        warn("Self-signed certificates are not trusted by browsers.")
        warn("Use only for development or testing.")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssl_cli.command(name="certbot")
@click.argument("domain")
@click.option("--email", "-e", help="Email for Let's Encrypt notifications")
@click.option("--instance", "-i", help="Configure SSL for this instance")
@click.option("--nginx", is_flag=True, help="Generate and install Nginx configuration")
@click.pass_context
def ssl_certbot(ctx, domain, email, instance, nginx):
    """Install Let's Encrypt certificate using certbot.

    Example: odoo-manager ssl certbot odoo.example.com --email admin@example.com --instance production
    """
    try:
        ssl_mgr = SSLManager()
        cert_info = ssl_mgr.install_certbot(domain, email)

        success(f"Let's Encrypt certificate installed for '{domain}'")
        console.print(f"  Certificate: {cert_info.cert_path}")
        console.print(f"  Private key: {cert_info.key_path}")
        console.print(f"  Valid until: {cert_info.valid_until.strftime('%Y-%m-%d')}")

        # Configure instance if specified
        if instance:
            inst_mgr = InstanceManager()
            inst = inst_mgr.get_instance(instance)

            # Update instance config
            instances_config = inst_mgr.instances_file.load()
            inst_config = instances_config.get_instance(instance)

            inst_config.ssl_enabled = True
            inst_config.ssl_domain = domain
            inst_config.ssl_cert_path = str(cert_info.cert_path)
            inst_config.ssl_key_path = str(cert_info.key_path)

            inst_mgr.instances_file.save(instances_config)
            success(f"Instance '{instance}' configured for SSL")

        # Configure Nginx if requested
        if nginx:
            nginx_conf = NginxConfig()
            config_content = nginx_conf.generate_config(
                instance_name=instance or domain,
                domain=domain,
                ssl_enabled=True,
                ssl_cert=cert_info.cert_path,
                ssl_key=cert_info.key_path,
            )

            if instance:
                nginx_conf.install_config(instance, domain, config_content)
            else:
                console.print("\n[cyan]Nginx Configuration:[/cyan]")
                console.print(config_content)
                info("Save this to /etc/nginx/sites-available/odoo-<instance>")
                info("Then create a symlink in /etc/nginx/sites-enabled/ and reload nginx")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssl_cli.command(name="import")
@click.argument("domain")
@click.option("--cert", "-c", required=True, help="Path to certificate file")
@click.option("--key", "-k", required=True, help="Path to private key file")
@click.pass_context
def ssl_import(ctx, domain, cert, key):
    """Import a custom certificate.

    Example: odoo-manager ssl import odoo.example.com --cert /path/to/cert.pem --key /path/to/key.pem
    """
    try:
        ssl_mgr = SSLManager()
        cert_path = Path(cert)
        key_path = Path(key)

        cert_info = ssl_mgr.import_certificate(domain, cert_path, key_path)

        success(f"Certificate imported for '{domain}'")
        console.print(f"  Certificate: {cert_info.cert_path}")
        console.print(f"  Private key: {cert_info.key_path}")
        console.print(f"  Issuer: {cert_info.issuer}")
        console.print(f"  Valid until: {cert_info.valid_until.strftime('%Y-%m-%d')}")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssl_cli.command(name="renew")
@click.argument("domain")
@click.pass_context
def ssl_renew(ctx, domain):
    """Renew a Let's Encrypt certificate.

    Example: odoo-manager ssl renew odoo.example.com
    """
    try:
        ssl_mgr = SSLManager()

        if ssl_mgr.renew_certificate(domain):
            success(f"Certificate renewed for '{domain}'")
        else:
            error(f"Failed to renew certificate for '{domain}'")
            ctx.exit(1)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssl_cli.command(name="status")
@click.argument("domain")
@click.pass_context
def ssl_status(ctx, domain):
    """Show certificate status for a domain.

    Example: odoo-manager ssl status odoo.example.com
    """
    try:
        ssl_mgr = SSLManager()
        cert_info = ssl_mgr.get_certificate(domain)

        if not cert_info:
            info(f"No certificate found for '{domain}'")
            return

        console.print(f"[bold]Certificate: {domain}[/bold]")
        console.print(f"Type: {cert_info.type}")
        console.print(f"Issuer: {cert_info.issuer}")
        console.print(f"Valid from: {cert_info.valid_from.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"Valid until: {cert_info.valid_until.strftime('%Y-%m-%d %H:%M:%S')}")

        # Check if expiring soon
        from datetime import timedelta

        days_left = (cert_info.valid_until - cert_info.valid_from.replace(tzinfo=None)).days
        if days_left < 30:
            warn(f"Certificate expires in {days_left} days!")
        else:
            success(f"Certificate is valid (expires in {days_left} days)")

        console.print(f"Certificate: {cert_info.cert_path}")
        console.print(f"Private key: {cert_info.key_path}")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssl_cli.command(name="ls")
@click.pass_context
def ssl_list(ctx):
    """List all certificates.

    Example: odoo-manager ssl ls
    """
    try:
        ssl_mgr = SSLManager()
        certificates = ssl_mgr.list_certificates()

        if not certificates:
            info("No certificates found")
            return

        table = Table(title="SSL Certificates")
        table.add_column("Domain", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Expires", style="yellow")
        table.add_column("Auto-renew")

        from datetime import timedelta

        for cert in certificates:
            days_left = (cert.valid_until - cert.valid_from.replace(tzinfo=None)).days
            expires_str = f"{days_left} days"

            if days_left < 30:
                expires_str = f"[red]{expires_str}[/red]"
            elif days_left < 90:
                expires_str = f"[yellow]{expires_str}[/yellow]"

            renew_str = "Yes" if cert.auto_renew else "No"

            table.add_row(
                cert.domain,
                cert.type,
                expires_str,
                renew_str,
            )

        console.print(table)

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssl_cli.command(name="rm")
@click.argument("domain")
@click.confirmation_option(prompt="Are you sure you want to remove this certificate?")
@click.pass_context
def ssl_remove(ctx, domain):
    """Remove a certificate.

    Example: odoo-manager ssl rm old-domain.example.com
    """
    try:
        ssl_mgr = SSLManager()
        ssl_mgr.remove_certificate(domain)
        success(f"Certificate removed for '{domain}'")

    except Exception as e:
        error(str(e))
        ctx.exit(1)


@ssl_cli.command(name="nginx")
@click.argument("instance")
@click.option("--domain", "-d", required=True, help="Domain name")
@click.option("--ssl", is_flag=True, help="Enable SSL")
@click.option("--http-port", type=int, default=80, help="HTTP port")
@click.option("--https-port", type=int, default=443, help="HTTPS port")
@click.option("--dry-run", is_flag=True, help="Show config without installing")
@click.pass_context
def ssl_nginx(ctx, instance, domain, ssl, http_port, https_port, dry_run):
    """Generate Nginx configuration for an instance.

    Example: odoo-manager ssl nginx production --domain odoo.example.com --ssl
    """
    try:
        inst_mgr = InstanceManager()
        inst = inst_mgr.get_instance(instance)

        nginx_conf = NginxConfig()

        cert_path = None
        key_path = None

        if ssl:
            ssl_mgr = SSLManager()
            cert_info = ssl_mgr.get_certificate(domain)

            if not cert_info:
                error(f"No SSL certificate found for '{domain}'")
                info(f"Generate one with: odoo-manager ssl certbot {domain}")
                ctx.exit(1)

            cert_path = cert_info.cert_path
            key_path = cert_info.key_path

        config_content = nginx_conf.generate_config(
            instance_name=instance,
            domain=domain,
            ssl_enabled=ssl,
            ssl_cert=cert_path,
            ssl_key=key_path,
            odoo_port=inst.config.port,
        )

        if dry_run:
            console.print(f"[cyan]Nginx configuration for '{instance}':[/cyan]")
            console.print()
            console.print(config_content)
        else:
            nginx_conf.install_config(instance, domain, config_content)

            if nginx_conf.reload_nginx():
                success(f"Nginx configuration installed and reloaded for '{instance}'")
                info(f"Access your instance at: http{'s' if ssl else ''}://{domain}")
            else:
                error("Nginx configuration test failed")
                ctx.exit(1)

    except Exception as e:
        error(str(e))
        ctx.exit(1)
