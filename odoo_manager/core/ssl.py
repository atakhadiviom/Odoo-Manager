"""
SSL/TLS certificate management for Odoo Manager.
"""

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from odoo_manager.config import InstanceConfig
from odoo_manager.constants import DEFAULT_NGINX_HTTP_PORT, DEFAULT_NGINX_PORT, DEFAULT_SSL_CERT_DIR
from odoo_manager.core.instance import InstanceManager
from odoo_manager.exceptions import SSLError as OdooSSLError


class CertificateType(str, Enum):
    """Types of SSL certificates."""

    SELF_SIGNED = "self-signed"
    LETS_ENCRYPT = "lets-encrypt"
    CUSTOM = "custom"


@dataclass
class CertificateInfo:
    """Information about an SSL certificate."""

    domain: str
    cert_path: Path
    key_path: Path
    type: CertificateType
    valid_from: datetime
    valid_until: datetime
    issuer: str
    auto_renew: bool = False


class SSLManager:
    """Manages SSL certificates for Odoo instances."""

    def __init__(self, cert_dir: Optional[Path] = None):
        """Initialize the SSL manager.

        Args:
            cert_dir: Directory to store certificates.
        """
        self.cert_dir = cert_dir or DEFAULT_SSL_CERT_DIR
        self.cert_dir.mkdir(parents=True, exist_ok=True)

    def generate_self_signed(
        self,
        domain: str,
        validity_days: int = 365,
    ) -> CertificateInfo:
        """Generate a self-signed certificate.

        Args:
            domain: Domain name for the certificate.
            validity_days: Number of days the certificate is valid.

        Returns:
            CertificateInfo with certificate details.
        """
        cert_path = self.cert_dir / f"{domain}.crt"
        key_path = self.cert_dir / f"{domain}.key"

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        # Create certificate
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Odoo Manager"),
                x509.NameAttribute(NameOID.COMMON_NAME, domain),
            ]
        )

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(
                datetime.utcnow()
                + datetime.timedelta(days=validity_days)
            )
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(domain)]),
                critical=False,
            )
            .sign(private_key, hashes.SHA256(), default_backend())
        )

        # Write certificate
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        # Write private key
        with open(key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        return CertificateInfo(
            domain=domain,
            cert_path=cert_path,
            key_path=key_path,
            type=CertificateType.SELF_SIGNED,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + datetime.timedelta(days=validity_days),
            issuer="Odoo Manager (Self-signed)",
        )

    def install_certbot(
        self,
        domain: str,
        email: Optional[str] = None,
    ) -> CertificateInfo:
        """Install certificate using Let's Encrypt (certbot).

        Args:
            domain: Domain name.
            email: Email for Let's Encrypt notifications.

        Returns:
            CertificateInfo with certificate details.

        Raises:
            SSLError: If certbot is not installed or fails.
        """
        # Check if certbot is installed
        try:
            subprocess.run(
                ["certbot", "--version"],
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise OdooSSLError(
                "certbot is not installed. Install it with: "
                "apt-get install certbot (Ubuntu/Debian) or "
                "brew install certbot (macOS)"
            )

        cert_path = self.cert_dir / f"{domain}.crt"
        key_path = self.cert_dir / f"{domain}.key"

        # Build certbot command
        cmd = [
            "certbot",
            "certonly",
            "--standalone",
            "-d", domain,
            "--cert-prefix", str(self.cert_dir / domain),
        ]

        if email:
            cmd.extend(["--email", email, "--agree-tos"])
        else:
            cmd.extend(["--register-unsafely-without-email"])

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise OdooSSLError(f"certbot failed: {e}") from e

        # Certbot creates files with different names
        actual_cert = self.cert_dir / "live" / domain / "fullchain.pem"
        actual_key = self.cert_dir / "live" / domain / "privkey.pem"

        if not actual_cert.exists() or not actual_key.exists():
            raise OdooSSLError("Certificate files not found after certbot run")

        # Create symlinks to expected locations
        if cert_path.exists():
            cert_path.unlink()
        if key_path.exists():
            key_path.unlink()

        cert_path.symlink_to(actual_cert)
        key_path.symlink_to(actual_key)

        # Read certificate to get info
        with open(actual_cert, "rb") as f:
            cert_data = x509.load_pem_x509_certificate(f.read(), default_backend())

        return CertificateInfo(
            domain=domain,
            cert_path=cert_path,
            key_path=key_path,
            type=CertificateType.LETS_ENCRYPT,
            valid_from=cert_data.not_valid_before.replace(tzinfo=None),
            valid_until=cert_data.not_valid_after.replace(tzinfo=None),
            issuer=cert_data.issuer.rfc4514_string(),
            auto_renew=True,
        )

    def import_certificate(
        self,
        domain: str,
        cert_path: Path,
        key_path: Path,
    ) -> CertificateInfo:
        """Import a custom certificate.

        Args:
            domain: Domain name.
            cert_path: Path to certificate file.
            key_path: Path to private key file.

        Returns:
            CertificateInfo with certificate details.
        """
        if not cert_path.exists():
            raise OdooSSLError(f"Certificate file not found: {cert_path}")
        if not key_path.exists():
            raise OdooSSLError(f"Private key file not found: {key_path}")

        # Copy to cert directory
        target_cert = self.cert_dir / f"{domain}.crt"
        target_key = self.cert_dir / f"{domain}.key"

        import shutil

        shutil.copy(cert_path, target_cert)
        shutil.copy(key_path, target_key)

        # Read certificate to get info
        with open(target_cert, "rb") as f:
            cert_data = x509.load_pem_x509_certificate(f.read(), default_backend())

        return CertificateInfo(
            domain=domain,
            cert_path=target_cert,
            key_path=target_key,
            type=CertificateType.CUSTOM,
            valid_from=cert_data.not_valid_before.replace(tzinfo=None),
            valid_until=cert_data.not_valid_after.replace(tzinfo=None),
            issuer=cert_data.issuer.rfc4514_string(),
        )

    def get_certificate(self, domain: str) -> Optional[CertificateInfo]:
        """Get certificate information for a domain.

        Args:
            domain: Domain name.

        Returns:
            CertificateInfo or None if not found.
        """
        cert_path = self.cert_dir / f"{domain}.crt"
        key_path = self.cert_dir / f"{domain}.key"

        if not cert_path.exists() or not key_path.exists():
            return None

        try:
            with open(cert_path, "rb") as f:
                cert_data = x509.load_pem_x509_certificate(f.read(), default_backend())

            return CertificateInfo(
                domain=domain,
                cert_path=cert_path,
                key_path=key_path,
                type=CertificateType.CUSTOM,  # We can't determine type from file alone
                valid_from=cert_data.not_valid_before.replace(tzinfo=None),
                valid_until=cert_data.not_valid_after.replace(tzinfo=None),
                issuer=cert_data.issuer.rfc4514_string(),
            )
        except Exception:
            return None

    def renew_certificate(self, domain: str) -> bool:
        """Renew a certificate (for Let's Encrypt).

        Args:
            domain: Domain name.

        Returns:
            True if renewed successfully.
        """
        cert_info = self.get_certificate(domain)

        if not cert_info or cert_info.type != CertificateType.LETS_ENCRYPT:
            raise OdooSSLError(f"Cannot renew certificate for {domain}")

        try:
            subprocess.run(
                ["certbot", "renew", "--cert-name", domain],
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def list_certificates(self) -> list[CertificateInfo]:
        """List all certificates.

        Returns:
            List of CertificateInfo objects.
        """
        certificates = []

        for cert_file in self.cert_dir.glob("*.crt"):
            if cert_file.is_symlink():
                continue

            domain = cert_file.stem
            cert_info = self.get_certificate(domain)
            if cert_info:
                certificates.append(cert_info)

        return certificates

    def remove_certificate(self, domain: str) -> None:
        """Remove certificate for a domain.

        Args:
            domain: Domain name.
        """
        cert_path = self.cert_dir / f"{domain}.crt"
        key_path = self.cert_dir / f"{domain}.key"

        if cert_path.exists():
            cert_path.unlink()

        if key_path.exists():
            key_path.unlink()


class NginxConfig:
    """Manages Nginx reverse proxy configuration for Odoo."""

    def __init__(self, config_dir: Path = Path("/etc/nginx/sites-available")):
        """Initialize Nginx configuration manager.

        Args:
            config_dir: Directory for Nginx configurations.
        """
        self.config_dir = config_dir
        self.enabled_dir = Path("/etc/nginx/sites-enabled")

    def generate_config(
        self,
        instance_name: str,
        domain: str,
        ssl_enabled: bool = True,
        ssl_cert: Optional[Path] = None,
        ssl_key: Optional[Path] = None,
        odoo_port: int = 8069,
    ) -> str:
        """Generate Nginx configuration for an instance.

        Args:
            instance_name: Odoo instance name.
            domain: Domain name.
            ssl_enabled: Whether to enable SSL.
            ssl_cert: Path to SSL certificate.
            ssl_key: Path to SSL private key.
            odoo_port: Odoo port.

        Returns:
            Generated configuration content.
        """
        if ssl_enabled:
            cert_path = ssl_cert or Path(f"/etc/ssl/certs/{domain}.crt")
            key_path = ssl_key or Path(f"/etc/ssl/private/{domain}.key")

            return f"""
# Odoo instance: {instance_name}
# Domain: {domain}

# HTTP redirect to HTTPS
server {{
    listen 80;
    server_name {domain};

    location / {{
        return 301 https://$host$request_uri;
    }}
}}

# HTTPS server
server {{
    listen {DEFAULT_NGINX_PORT} ssl http2;
    server_name {domain};

    # SSL configuration
    ssl_certificate {cert_path};
    ssl_certificate_key {key_path};

    # SSL security settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES128-GCM-SHA256;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Logging
    access_log /var/log/nginx/{instance_name}-access.log;
    error_log /var/log/nginx/{instance_name}-error.log;

    # Proxy settings
    proxy_read_timeout 720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;

    # Increase buffer sizes for large Odoo responses
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;

    # Odoo proxy configuration
    location / {{
        proxy_pass http://127.0.0.1:{odoo_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }}

    # Longpolling
    location /longpolling {{
        proxy_pass http://127.0.0.1:{odoo_port + 3};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
        else:
            return f"""
# Odoo instance: {instance_name}
# Domain: {domain}

server {{
    listen 80;
    server_name {domain};

    # Logging
    access_log /var/log/nginx/{instance_name}-access.log;
    error_log /var/log/nginx/{instance_name}-error.log;

    # Proxy settings
    proxy_read_timeout 720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;

    # Increase buffer sizes
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;

    # Odoo proxy configuration
    location / {{
        proxy_pass http://127.0.0.1:{odoo_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }}
}}
"""

    def install_config(self, instance_name: str, domain: str, config_content: str) -> None:
        """Install Nginx configuration for an instance.

        Args:
            instance_name: Odoo instance name.
            domain: Domain name.
            config_content: Nginx configuration content.
        """
        config_file = self.config_dir / f"odoo-{instance_name}"

        # Write configuration
        config_file.write_text(config_content)

        # Enable site
        self.enabled_dir.mkdir(parents=True, exist_ok=True)
        link = self.enabled_dir / f"odoo-{instance_name}"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(config_file)

    def remove_config(self, instance_name: str) -> None:
        """Remove Nginx configuration for an instance.

        Args:
            instance_name: Odoo instance name.
        """
        config_file = self.config_dir / f"odoo-{instance_name}"
        link = self.enabled_dir / f"odoo-{instance_name}"

        if link.exists() or link.is_symlink():
            link.unlink()

        if config_file.exists():
            config_file.unlink()

    def reload_nginx(self) -> bool:
        """Reload Nginx configuration.

        Returns:
            True if reloaded successfully.
        """
        try:
            subprocess.run(
                ["nginx", "-t"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["systemctl", "reload", "nginx"],
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
