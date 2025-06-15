"""CLI commands for SSL/TLS certificate management."""

import sys
from typing import Optional

import click

from .cli_environments import _get_config_manager
from .config.certificates import CertificateMode
from .config.manager import ConfigurationManager


@click.group()
def certificates() -> None:
    """SSL/TLS certificate management commands."""
    pass


@certificates.command("provision")
@click.option(
    "--domain",
    "-d",
    help="Domain name for certificate (defaults to current environment domain)",
)
@click.option("--email", "-e", help="Email for Let's Encrypt registration")
@click.option(
    "--san",
    multiple=True,
    help="Subject Alternative Names (can be used multiple times)",
)
@click.option(
    "--production",
    is_flag=True,
    help="Use production Let's Encrypt (default: current environment mode)",
)
@click.option("--self-signed", is_flag=True, help="Create self-signed certificate")
@click.option("--staging", is_flag=True, help="Use Let's Encrypt staging")
@click.option("--environment", "-env", help="Target environment (defaults to current)")
@click.option("--force", is_flag=True, help="Force certificate creation even if exists")
def provision_certificate(
    domain: Optional[str],
    email: Optional[str],
    san: tuple,
    production: bool,
    self_signed: bool,
    staging: bool,
    environment: Optional[str],
    force: bool,
) -> None:
    """Provision SSL/TLS certificate for a domain."""
    try:
        config_manager = _get_config_manager()

        # Get target environment
        if environment:
            env = config_manager.get_environment(environment)
            if not env:
                click.echo(f"Environment '{environment}' not found", err=True)
                sys.exit(1)
        else:
            env = config_manager.get_current_environment()

        # Use environment defaults if not specified
        target_domain = domain or env.domain
        target_email = email or env.admin_email

        # Determine certificate mode
        if self_signed:
            mode = CertificateMode.SELF_SIGNED
        elif production:
            mode = CertificateMode.PRODUCTION
        elif staging:
            mode = CertificateMode.STAGING
        else:
            # Use environment default
            mode_mapping = {
                "self_signed": CertificateMode.SELF_SIGNED,
                "le_staging": CertificateMode.STAGING,
                "le_production": CertificateMode.PRODUCTION,
            }
            mode = mode_mapping.get(env.certificate_mode, CertificateMode.SELF_SIGNED)

        # Get environment-specific certificate manager
        cert_manager = config_manager.get_environment_certificate_manager(env.name)

        # Create certificate configuration with environment-specific paths
        from .config.certificates import CertificateConfig

        cert_base_path = str(cert_manager.base_path / target_domain)
        cert_config = CertificateConfig(
            domain=target_domain,
            email=target_email,
            mode=mode,
            san_domains=(
                list(san)
                if san
                else [
                    f"mail.{target_domain}",
                    f"www.{target_domain}",
                    f"dns.{target_domain}",
                ]
            ),
            cert_path=f"{cert_base_path}/cert.pem",
            key_path=f"{cert_base_path}/privkey.pem",
            fullchain_path=f"{cert_base_path}/fullchain.pem",
        )

        # Check if certificate already exists
        if not force and cert_manager._validate_existing_certificate(cert_config):
            click.echo(
                f"Certificate already exists for {target_domain} in environment "
                f"'{env.name}'. Use --force to recreate."
            )
            return

        # Provision certificate
        # Build mode description for output
        default_or_override = (
            "environment default"
            if not any([self_signed, production, staging])
            else "override"
        )  # noqa: E501
        mode_desc = f"{mode.value} ({default_or_override})"
        provision_msg = f"Provisioning {mode_desc} certificate for {target_domain} in environment '{env.name}'..."  # noqa: E501
        click.echo(provision_msg)
        if cert_config.san_domains:
            san_list = ", ".join(cert_config.san_domains)
            click.echo(f"Subject Alternative Names: {san_list}")

        success = cert_manager.provision_certificate(cert_config)

        if success:
            click.echo(f"✅ Certificate successfully provisioned for {target_domain}")
            click.echo(f"Environment: {env.name}")
            click.echo(f"Certificate path: {cert_config.cert_path}")
            click.echo(f"Private key path: {cert_config.key_path}")
            click.echo(f"Full chain path: {cert_config.fullchain_path}")
        else:
            click.echo(
                f"❌ Failed to provision certificate for {target_domain}", err=True
            )
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@certificates.command("renew")
@click.option("--domain", "-d", help="Domain name to renew")
@click.option("--all", is_flag=True, help="Renew all certificates")
def renew_certificate(domain: Optional[str], all: bool) -> None:
    """Renew SSL/TLS certificates."""
    try:
        if not domain and not all:
            click.echo("Error: Must specify either --domain or --all", err=True)
            sys.exit(1)

        config_manager = _get_config_manager()
        cert_manager = config_manager.cert_manager

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
@click.option("--environment", "-env", help="Target environment (defaults to current)")
@click.option(
    "--all-environments", is_flag=True, help="List certificates from all environments"
)
def list_certificates(
    detailed: bool, environment: Optional[str], all_environments: bool
) -> None:
    """List managed certificates for current or specified environment(s)."""
    try:
        config_manager = _get_config_manager()

        if all_environments:
            # List certificates from all environments
            all_certs = []
            for env in config_manager.list_environments():
                try:
                    cert_manager = config_manager.get_environment_certificate_manager(
                        env.name
                    )
                    certificates = cert_manager.list_certificates()
                    for cert_info in certificates:
                        cert_info["environment"] = env.name
                        cert_info["cert_mode"] = env.certificate_mode
                    all_certs.extend(certificates)
                except Exception:  # nosec B112
                    # Skip environments with no certificates or configuration issues
                    continue

            if not all_certs:
                click.echo("No certificates found in any environment.")
                return

            click.echo(
                f"Found {len(all_certs)} certificate(s) across all " "environments:"
            )
            click.echo()

            for cert_info in all_certs:
                domain = cert_info["domain"]
                status = cert_info["status"]
                env_name = cert_info["environment"]
                cert_mode = cert_info["cert_mode"]

                status_emoji = "✅" if status == "valid" else "❌"
                click.echo(f"{status_emoji} {domain} ({env_name} - {cert_mode})")

                if detailed:
                    click.echo(f"   Environment: {env_name}")
                    click.echo(f"   Certificate Mode: {cert_mode}")
                    click.echo(f"   Status: {status}")
                    click.echo(f"   Certificate: {cert_info['cert_path']}")
                    click.echo()

        else:
            # Get target environment
            if environment:
                env = config_manager.get_environment(environment)
                if not env:
                    click.echo(f"Environment '{environment}' not found", err=True)
                    sys.exit(1)
            else:
                env = config_manager.get_current_environment()

            cert_manager = config_manager.get_environment_certificate_manager(env.name)
            certificates = cert_manager.list_certificates()

            if not certificates:
                click.echo(f"No certificates found in environment '{env.name}'.")
                return

            click.echo(
                f"Found {len(certificates)} certificate(s) in environment "
                f"'{env.name}' (mode" + ": " + f"{env.certificate_mode})" + ":"
            )
            click.echo()

            for cert_info in certificates:
                domain = cert_info["domain"]
                status = cert_info["status"]
                cert_path = cert_info["cert_path"]

                status_emoji = "✅" if status == "valid" else "❌"
                click.echo(f"{status_emoji} {domain}")

                if detailed:
                    click.echo(f"   Environment: {env.name}")
                    click.echo(f"   Certificate Mode: {env.certificate_mode}")
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
        config_manager = _get_config_manager()
        cert_manager = config_manager.cert_manager
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
        config_manager = _get_config_manager()
        cert_manager = config_manager.cert_manager

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
                mode=(
                    CertificateMode.PRODUCTION
                    if production
                    else CertificateMode.STAGING
                ),
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


@certificates.command("provision-environment")
@click.option("--environment", "-env", help="Target environment (defaults to current)")
@click.option("--force", is_flag=True, help="Force certificate creation even if exists")
def provision_environment_certificates(environment: Optional[str], force: bool) -> None:
    """Provision certificates for an environment based on its default mode."""
    try:
        config_manager = _get_config_manager()

        # Get target environment
        if environment:
            env = config_manager.get_environment(environment)
            if not env:
                click.echo(f"Environment '{environment}' not found", err=True)
                sys.exit(1)
        else:
            env = config_manager.get_current_environment()

        click.echo(
            f"Provisioning certificates for environment '{env.name}' "
            f"using mode '{env.certificate_mode}'..."
        )
        success = config_manager.provision_environment_certificates(
            env.name, force=force
        )

        if success:
            click.echo(
                f"✅ Successfully provisioned certificates for environment '{env.name}'"
            )
        else:
            click.echo(
                f"❌ Failed to provision certificates for environment '{env.name}'",
                err=True,
            )
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@certificates.command("provision-all-environments")
@click.option("--force", is_flag=True, help="Force certificate creation even if exists")
@click.option(
    "--enabled-only", is_flag=True, help="Only provision for enabled environments"
)
def provision_all_environment_certificates(force: bool, enabled_only: bool) -> None:
    """Provision certificates for all environments based on their default modes."""
    try:
        config_manager = _get_config_manager()
        environments = config_manager.list_environments()

        if enabled_only:
            environments = [env for env in environments if env.enabled]

        if not environments:
            click.echo("No environments found to provision certificates for.")
            return

        click.echo(
            f"Provisioning certificates for {len(environments)} environment(s)..."
        )
        success_count = 0

        for env in environments:
            click.echo(
                f"\n--- Environment: {env.name} (mode: {env.certificate_mode}) ---"
            )
            try:
                success = config_manager.provision_environment_certificates(
                    env.name, force=force
                )
                if success:
                    click.echo(f"✅ Success for {env.name}")
                    success_count += 1
                else:
                    click.echo(f"❌ Failed for {env.name}")
            except Exception as e:
                click.echo(f"❌ Error for {env.name}: {e}")

        click.echo(
            f"\nProvisioning complete: {success_count}/"
            f"{len(environments)} environments successful"
        )

        if success_count == len(environments):
            click.echo("🎉 All environment certificates are ready!")
        else:
            click.echo("⚠️  Some environments failed certificate provisioning")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
