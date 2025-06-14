"""CLI commands for SSL/TLS certificate management."""

import sys
from typing import Optional

import click

from .config.certificates import CertificateMode, get_default_certificate_manager
from .config.manager import ConfigurationManager


@click.group()
def certificates() -> None:
    """SSL/TLS certificate management commands."""
    pass


@certificates.command("provision")
@click.option("--domain", "-d", required=True, help="Domain name for certificate")
@click.option("--email", "-e", help="Email for Let's Encrypt registration")
@click.option(
    "--san",
    multiple=True,
    help="Subject Alternative Names (can be used multiple times)",
)
@click.option(
    "--production", is_flag=True, help="Use production Let's Encrypt (default: staging)"
)
@click.option("--self-signed", is_flag=True, help="Create self-signed certificate")
@click.option("--force", is_flag=True, help="Force certificate creation even if exists")
def provision_certificate(
    domain: str,
    email: Optional[str],
    san: tuple,
    production: bool,
    self_signed: bool,
    force: bool,
) -> None:
    """Provision SSL/TLS certificate for a domain."""
    try:
        cert_manager = get_default_certificate_manager()

        # Get email from configuration if not provided
        if not email:
            config_manager = ConfigurationManager()
            email = config_manager.global_config.security.letsencrypt_email

        # Determine certificate mode
        if self_signed:
            mode = CertificateMode.SELF_SIGNED
        elif production:
            mode = CertificateMode.PRODUCTION
        else:
            mode = CertificateMode.STAGING

        # Create certificate configuration
        from .config.certificates import CertificateConfig

        cert_config = CertificateConfig(
            domain=domain,
            email=email,
            mode=mode,
            san_domains=list(san),
        )

        # Check if certificate already exists
        if not force:
            cert_path = cert_config.cert_path
            if cert_path and cert_manager._validate_existing_certificate(cert_config):
                click.echo(
                    f"Certificate already exists for {domain}. Use --force to recreate."
                )
                return

        # Provision certificate
        click.echo(f"Provisioning {mode.value} certificate for {domain}...")
        if san:
            click.echo(f"Subject Alternative Names: {', '.join(san)}")

        success = cert_manager.provision_certificate(cert_config)

        if success:
            click.echo(f"✅ Certificate successfully provisioned for {domain}")
            click.echo(f"Certificate path: {cert_config.cert_path}")
            click.echo(f"Private key path: {cert_config.key_path}")
            click.echo(f"Full chain path: {cert_config.fullchain_path}")
        else:
            click.echo(f"❌ Failed to provision certificate for {domain}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@certificates.command("renew")
@click.option("--domain", "-d", required=True, help="Domain name to renew")
@click.option("--all", is_flag=True, help="Renew all certificates")
def renew_certificate(domain: str, all: bool) -> None:
    """Renew SSL/TLS certificates."""
    try:
        cert_manager = get_default_certificate_manager()

        if all:
            click.echo("Renewing all certificates...")
            certificates = cert_manager.list_certificates()

            renewed_count = 0
            for cert_info in certificates:
                cert_domain = cert_info["domain"]
                config_manager = ConfigurationManager()
                email = config_manager.global_config.security.letsencrypt_email

                cert_config = cert_manager.get_certificate_for_domain(
                    cert_domain, email, production_mode=False
                )

                if cert_manager.renew_certificate(cert_config):
                    click.echo(f"✅ Renewed certificate for {cert_domain}")
                    renewed_count += 1
                else:
                    click.echo(
                        f"⚠️  Certificate for {cert_domain} did not need renewal"
                        " or failed"
                    )

            click.echo(f"Renewed {renewed_count} certificates")
        else:
            click.echo(f"Renewing certificate for {domain}...")
            config_manager = ConfigurationManager()
            email = config_manager.global_config.security.letsencrypt_email

            cert_config = cert_manager.get_certificate_for_domain(
                domain, email, production_mode=False
            )

            success = cert_manager.renew_certificate(cert_config)

            if success:
                click.echo(f"✅ Certificate renewed for {domain}")
            else:
                click.echo(
                    f"⚠️  Certificate for {domain} did not need renewal"
                    " or renewal failed"
                )

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@certificates.command("list")
@click.option("--detailed", is_flag=True, help="Show detailed certificate information")
def list_certificates(detailed: bool) -> None:
    """List all managed certificates."""
    try:
        cert_manager = get_default_certificate_manager()
        certificates = cert_manager.list_certificates()

        if not certificates:
            click.echo("No certificates found.")
            return

        click.echo(f"Found {len(certificates)}" + " certificate(s):")
        click.echo()

        for cert_info in certificates:
            domain = cert_info["domain"]
            status = cert_info["status"]
            cert_path = cert_info["cert_path"]

            status_emoji = "✅" if status == "valid" else "❌"
            click.echo(f"{status_emoji} {domain}")

            if detailed:
                click.echo(f"   Status: {status}")
                click.echo(f"   Certificate: {cert_path}")
                click.echo()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@certificates.command("validate")
@click.option("--domain", "-d", required=True, help="Domain name to validate")
def validate_certificate(domain: str) -> None:
    """Validate a certificate for a domain."""
    try:
        cert_manager = get_default_certificate_manager()
        config_manager = ConfigurationManager()
        email = config_manager.global_config.security.letsencrypt_email

        cert_config = cert_manager.get_certificate_for_domain(
            domain, email, production_mode=False
        )

        # Force existing mode for validation
        cert_config.mode = CertificateMode.EXISTING

        if cert_manager._validate_existing_certificate(cert_config):
            click.echo(f"✅ Certificate for {domain} is valid")
        else:
            click.echo(f"❌ Certificate for {domain} is invalid or missing")
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@certificates.command("setup")
@click.option(
    "--production",
    is_flag=True,
    help="Setup production certificates (default: staging)",
)
@click.option("--email", "-e", help="Email for Let's Encrypt registration")
@click.option("--force", is_flag=True, help="Force setup even if certificates exist")
def setup_certificates(production: bool, email: Optional[str], force: bool) -> None:
    """Setup certificates for all configured domains."""
    try:
        config_manager = ConfigurationManager()
        cert_manager = get_default_certificate_manager()

        # Get email from configuration if not provided
        if not email:
            email = config_manager.global_config.security.letsencrypt_email

        # Get all configured domains
        domains_config = config_manager.domains_config

        if not domains_config.domains:
            click.echo("No domains configured. Please add domains first.")
            return

        mode = "production" if production else "staging"
        click.echo(f"Setting up {mode} certificates for all configured domains...")

        success_count = 0
        for domain_config in domains_config.domains:
            domain = domain_config.name

            # Create SAN domains from A records
            san_domains = []
            for subdomain in domain_config.a_records.keys():
                if subdomain not in ["@", ""]:
                    san_domains.append(f"{subdomain}.{domain}")

            from .config.certificates import CertificateConfig

            cert_config = CertificateConfig(
                domain=domain,
                email=email,
                mode=CertificateMode.PRODUCTION
                if production
                else CertificateMode.STAGING,
                san_domains=san_domains,
            )

            # Check if certificate already exists
            if not force and cert_manager._validate_existing_certificate(cert_config):
                click.echo(f"✅ Certificate already exists for {domain}")
                success_count += 1
                continue

            click.echo(f"Provisioning certificate for {domain}...")
            if cert_manager.provision_certificate(cert_config):
                click.echo(f"✅ Certificate provisioned for {domain}")
                success_count += 1
            else:
                click.echo(f"❌ Failed to provision certificate for {domain}")

        click.echo(
            f"\nSetup complete: {success_count}"
            + "/"
            + f"{len(domains_config.domains)} certificates ready"
        )

        if success_count == len(domains_config.domains):
            click.echo("🎉 All certificates are ready!")
        else:
            click.echo("⚠️  Some certificates failed to provision")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
