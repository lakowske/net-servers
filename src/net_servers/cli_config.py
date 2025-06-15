"""CLI commands for configuration management."""

import click

from .actions.container import ContainerManager
from .config.containers import get_container_config
from .config.manager import ConfigurationManager
from .config.schemas import DomainConfig, UserConfig
from .config.sync import (
    ApacheServiceSynchronizer,
    ConfigurationSyncManager,
    DnsServiceSynchronizer,
    MailServiceSynchronizer,
)


def setup_sync_manager(base_path: str = "/data") -> ConfigurationSyncManager:
    """Set up configuration sync manager with all services."""
    config_manager = ConfigurationManager(base_path=base_path)
    sync_manager = ConfigurationSyncManager(config_manager)

    # Register synchronizers for running containers
    try:
        # Mail service
        mail_config = get_container_config("mail", use_config_manager=True)
        mail_container = ContainerManager(mail_config)
        mail_sync = MailServiceSynchronizer(config_manager, mail_container)
        sync_manager.register_synchronizer("mail", mail_sync)

        # DNS service
        dns_config = get_container_config("dns", use_config_manager=True)
        dns_container = ContainerManager(dns_config)
        dns_sync = DnsServiceSynchronizer(config_manager, dns_container)
        sync_manager.register_synchronizer("dns", dns_sync)

        # Apache service
        apache_config = get_container_config("apache", use_config_manager=True)
        apache_container = ContainerManager(apache_config)
        apache_sync = ApacheServiceSynchronizer(config_manager, apache_container)
        sync_manager.register_synchronizer("apache", apache_sync)

    except Exception as e:
        click.echo(f"Warning: Could not initialize all service synchronizers: {e}")

    return sync_manager


@click.group()
def config() -> None:
    """Configuration management commands."""
    pass


@config.group()
def user() -> None:
    """User management commands."""
    pass


@user.command("add")
@click.option("--username", "-u", required=True, help="Username")
@click.option("--email", "-e", required=True, help="Email address")
@click.option("--domain", "-d", multiple=True, help="Domains (can specify multiple)")
@click.option("--role", "-r", multiple=True, default=["user"], help="User roles")
@click.option("--quota", "-q", default="500M", help="Mailbox quota")
@click.option("--base-path", default="/data", help="Configuration base path")
def add_user(
    username: str,
    email: str,
    domain: tuple,
    role: tuple,
    quota: str,
    base_path: str,
) -> None:
    """Add a new user to the system."""
    try:
        # Create user configuration
        user_config = UserConfig(
            username=username,
            email=email,
            domains=list(domain) if domain else ["local.dev"],
            roles=list(role),
            mailbox_quota=quota,
        )

        # Set up sync manager
        sync_manager = setup_sync_manager(base_path)

        # Add user
        if sync_manager.add_user(user_config):
            click.echo(f"✓ Successfully added user: {username}")

            # Validate configuration
            validation_results = sync_manager.validate_all_services()
            for service, errors in validation_results.items():
                if errors:
                    click.echo(
                        f"⚠ Validation warnings for {service}: {', '.join(errors)}"
                    )
                else:
                    click.echo(f"✓ {service} configuration validated")
        else:
            click.echo(f"✗ Failed to add user: {username}", err=True)

    except Exception as e:
        click.echo(f"✗ Error adding user: {e}", err=True)


@user.command()
@click.option("--username", "-u", required=True, help="Username to delete")
@click.option("--base-path", default="/data", help="Configuration base path")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def delete(username: str, base_path: str, confirm: bool) -> None:
    """Delete a user from the system."""
    try:
        if not confirm:
            if not click.confirm(
                f"Are you sure you want to delete user '{username}' and their mailbox?"
            ):
                click.echo("Operation cancelled.")
                return

        # Set up sync manager
        sync_manager = setup_sync_manager(base_path)

        # Delete user
        if sync_manager.delete_user(username):
            click.echo(f"✓ Successfully deleted user: {username}")
        else:
            click.echo(f"✗ Failed to delete user: {username}", err=True)

    except Exception as e:
        click.echo(f"✗ Error deleting user: {e}", err=True)


@user.command("list")
@click.option("--base-path", default="/data", help="Configuration base path")
def list_users(base_path: str) -> None:
    """List all users in the system."""
    try:
        config_manager = ConfigurationManager(base_path)
        users = config_manager.users_config.users

        if not users:
            click.echo("No users found.")
            return

        click.echo(f"Found {len(users)} users" + ":")
        click.echo()

        for user in users:
            status = "✓ Enabled" if user.enabled else "✗ Disabled"
            click.echo(f"Username: {user.username}")
            click.echo(f"  Email: {user.email}")
            click.echo(f"  Domains: {', '.join(user.domains)}")
            click.echo(f"  Roles: {', '.join(user.roles)}")
            click.echo(f"  Quota: {user.mailbox_quota}")
            click.echo(f"  Status: {status}")
            click.echo()

    except Exception as e:
        click.echo(f"✗ Error listing users: {e}", err=True)


@config.group()
def domain() -> None:
    """Domain management commands."""
    pass


@domain.command("add")
@click.option("--name", "-n", required=True, help="Domain name")
@click.option("--mx", "-m", multiple=True, help="MX records")
@click.option("--a-record", "-a", multiple=True, help="A records (format: name:ip)")
@click.option("--base-path", default="/data", help="Configuration base path")
def add_domain(name: str, mx: tuple, a_record: tuple, base_path: str) -> None:
    """Add a new domain to the system."""
    try:
        # Parse A records
        a_records = {}
        for record in a_record:
            if ":" in record:
                record_name, ip = record.split(":", 1)
                a_records[record_name] = ip
            else:
                click.echo(
                    f"Invalid A record format: {record} (use name" + ":" + "ip)",
                    err=True,
                )
                return

        # Create domain configuration
        domain_config = DomainConfig(
            name=name,
            enabled=True,
            mx_records=list(mx) if mx else [],
            a_records=a_records,
        )

        # Set up configuration manager
        config_manager = ConfigurationManager(base_path)

        # Add domain
        current_domains = config_manager.domains_config
        current_domains.domains.append(domain_config)
        config_manager.save_domains_config(current_domains)

        # Sync to services
        sync_manager = setup_sync_manager(base_path)
        if sync_manager.sync_all_domains():
            click.echo(f"✓ Successfully added domain: {name}")
        else:
            click.echo(f"✗ Failed to sync domain to services: {name}", err=True)

    except Exception as e:
        click.echo(f"✗ Error adding domain: {e}", err=True)


@domain.command("list")
@click.option("--base-path", default="/data", help="Configuration base path")
def list_domains(base_path: str) -> None:
    """List all domains in the system."""
    try:
        config_manager = ConfigurationManager(base_path)
        domains = config_manager.domains_config.domains

        if not domains:
            click.echo("No domains found.")
            return

        click.echo(f"Found {len(domains)} domains" + ":")
        click.echo()

        for domain in domains:
            status = "✓ Enabled" if domain.enabled else "✗ Disabled"
            click.echo(f"Domain: {domain.name}")
            click.echo(f"  Status: {status}")
            if domain.mx_records:
                click.echo(f"  MX Records: {', '.join(domain.mx_records)}")
            if domain.a_records:
                a_records_str = ", ".join(
                    f"{name}" + ":" + f"{ip}" for name, ip in domain.a_records.items()
                )
                click.echo(f"  A Records: {a_records_str}")
            click.echo()

    except Exception as e:
        click.echo(f"✗ Error listing domains: {e}", err=True)


@config.command()
@click.option("--base-path", default="/data", help="Configuration base path")
def validate(base_path: str) -> None:
    """Validate configuration across all services."""
    try:
        sync_manager = setup_sync_manager(base_path)
        validation_results = sync_manager.validate_all_services()

        all_valid = True
        for service, errors in validation_results.items():
            if errors:
                all_valid = False
                click.echo(f"✗ {service} validation failed" + ":")
                for error in errors:
                    click.echo("  - " + f"{error}")
            else:
                click.echo(f"✓ {service} configuration is valid")

        if all_valid:
            click.echo("\n✓ All service configurations are valid")
        else:
            click.echo("\n✗ Some service configurations have issues", err=True)

    except Exception as e:
        click.echo(f"✗ Error validating configuration: {e}", err=True)


@config.command()
@click.option("--base-path", default="/data", help="Configuration base path")
def sync(base_path: str) -> None:
    """Synchronize configuration to all services."""
    try:
        sync_manager = setup_sync_manager(base_path)

        click.echo("Synchronizing users...")
        if sync_manager.sync_all_users():
            click.echo("✓ Users synchronized")
        else:
            click.echo("✗ Failed to sync users", err=True)

        click.echo("Synchronizing domains...")
        if sync_manager.sync_all_domains():
            click.echo("✓ Domains synchronized")
        else:
            click.echo("✗ Failed to sync domains", err=True)

        click.echo("Reloading services...")
        if sync_manager.reload_all_services():
            click.echo("✓ Services reloaded")
        else:
            click.echo("⚠ Some services failed to reload")

    except Exception as e:
        click.echo(f"✗ Error synchronizing configuration: {e}", err=True)


@config.command()
@click.option("--base-path", default="/data", help="Configuration base path")
def init(base_path: str) -> None:
    """Initialize default configuration files."""
    try:
        config_manager = ConfigurationManager(base_path)
        config_manager.initialize_default_configs()
        click.echo("✓ Default configuration initialized")

        # Show what was created
        click.echo("\nCreated configuration files:")
        config_files = [
            config_manager.paths.config_path / "global.yaml",
            config_manager.paths.config_path / "users.yaml",
            config_manager.paths.config_path / "domains.yaml",
            config_manager.paths.config_path / "services" / "services.yaml",
        ]

        for config_file in config_files:
            if config_file.exists():
                click.echo(f"  ✓ {config_file}")
            else:
                click.echo(f"  ✗ {config_file}")

    except Exception as e:
        click.echo(f"✗ Error initializing configuration: {e}", err=True)


@config.command()
@click.option("--to-email", "-t", required=True, help="Recipient email address")
@click.option("--subject", "-s", default="Test Email", help="Email subject")
@click.option("--body", "-b", default="This is a test email.", help="Email body")
@click.option("--base-path", default="/data", help="Configuration base path")
def test_email(to_email: str, subject: str, body: str, base_path: str) -> None:
    """Send a test email to verify mail service configuration."""
    try:
        import smtplib
        from email.mime.text import MIMEText

        # Create message
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = "admin@local.dev"
        msg["To"] = to_email

        # Send via SMTP
        with smtplib.SMTP("localhost", 25) as smtp:
            smtp.send_message(msg)

        click.echo(f"✓ Test email sent to {to_email}")
        click.echo("Check the recipient's mailbox to verify delivery.")

    except Exception as e:
        click.echo(f"✗ Failed to send test email: {e}", err=True)


@config.command()
@click.option("--base-path", default="/data", help="Configuration base path")
@click.option("--debounce", default=2.0, help="Debounce delay for file changes")
def daemon(base_path: str, debounce: float) -> None:
    """Run configuration daemon to watch for changes and auto-sync."""
    try:
        from .config.watcher import ConfigurationDaemon

        click.echo("Starting configuration daemon...")
        click.echo(f"Watching configuration path: {base_path}")
        click.echo("Press Ctrl+C to stop")

        daemon = ConfigurationDaemon(base_path, debounce)
        daemon.run()

    except KeyboardInterrupt:
        click.echo("\nDaemon stopped by user")
    except Exception as e:
        click.echo(f"✗ Daemon error: {e}", err=True)


if __name__ == "__main__":
    config()
