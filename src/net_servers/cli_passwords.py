"""CLI commands for password management."""

import getpass
import json
from typing import Optional, cast

import click

from .config.manager import ConfigurationManager
from .config.schemas import UsersConfig, load_yaml_config
from .config.secrets import PasswordManager


def _get_password_manager() -> PasswordManager:
    """Get password manager instance."""
    # First get the environments config to determine current environment
    from .cli_environments import _get_environments_config

    _, environments_config = _get_environments_config()
    current_env = None
    for env in environments_config.environments:
        if env.name == environments_config.current_environment:
            current_env = env
            break

    if not current_env:
        raise ValueError(
            f"Current environment '{environments_config.current_environment}' not found"
        )

    # Initialize config manager with current environment's base path
    config_manager = ConfigurationManager(base_path=current_env.base_path)
    secrets_file = config_manager.paths.config_path / "secrets.yaml"
    return PasswordManager(secrets_file)


def _get_users_config() -> UsersConfig:
    """Get users configuration."""
    # Use the same environment-aware approach
    from .cli_environments import _get_environments_config

    _, environments_config = _get_environments_config()
    current_env = None
    for env in environments_config.environments:
        if env.name == environments_config.current_environment:
            current_env = env
            break

    if not current_env:
        raise ValueError(
            f"Current environment '{environments_config.current_environment}' not found"
        )

    config_manager = ConfigurationManager(base_path=current_env.base_path)
    users_file = config_manager.paths.config_path / "users.yaml"
    return cast(UsersConfig, load_yaml_config(users_file, UsersConfig))


@click.group()
def passwords() -> None:
    """Manage user passwords and secrets."""
    pass


@passwords.command("init-user")
@click.option("--username", required=True, help="Username to initialize")
@click.option("--password", help="Password (will prompt if not provided)")
@click.option("--generate", is_flag=True, help="Generate a random password")
def init_user_password(username: str, password: Optional[str], generate: bool) -> None:
    """Initialize password for a user."""
    password_manager = _get_password_manager()
    users_config = _get_users_config()

    # Check if user exists in users.yaml
    user_exists = any(user.username == username for user in users_config.users)
    if user_exists is False:
        click.echo(f"Warning: User '{username}' not found in users.yaml")  # noqa: E713
        if click.confirm("Continue anyway?") is False:  # noqa: E713
            return

    # Handle password input
    if generate:
        password = None  # Let password manager generate one
    elif password is None:
        password = getpass.getpass(f"Enter password for {username}: ")
        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            click.echo("Passwords do not match!")
            return

    # Set the password
    final_password = password_manager.set_user_password(username, password)

    if generate or password is None:
        click.echo(f"Generated password for {username}: {final_password}")
        click.echo("Please save this password securely!")
    else:
        click.echo(f"Password set for user: {username}")


@passwords.command("change")
@click.option("--username", required=True, help="Username to change password for")
@click.option("--password", help="New password (will prompt if not provided)")
@click.option("--generate", is_flag=True, help="Generate a new random password")
def change_password(username: str, password: Optional[str], generate: bool) -> None:
    """Change password for a user."""
    password_manager = _get_password_manager()

    # Check if user exists in secrets
    user_info = password_manager.get_user_info(username)
    if user_info is None:
        click.echo(f"User '{username}' not found in secrets. Use 'init-user' first.")
        return

    # Handle password input
    if generate:
        password = None  # Let password manager generate one
    elif password is None:
        password = getpass.getpass(f"Enter new password for {username}: ")
        confirm_password = getpass.getpass("Confirm new password: ")
        if password != confirm_password:
            click.echo("Passwords do not match!")
            return

    # Change the password
    final_password = password_manager.set_user_password(username, password)

    if generate or password is None:
        click.echo(f"New password for {username}: {final_password}")
        click.echo("Please save this password securely!")
    else:
        click.echo(f"Password changed for user: {username}")


@passwords.command("set-service")
@click.option("--username", required=True, help="Username")
@click.option("--service", required=True, help="Service name (webdav, email, etc.)")
@click.option("--password", help="Service password (will prompt if not provided)")
def set_service_password(username: str, service: str, password: Optional[str]) -> None:
    """Set service-specific password for a user."""
    password_manager = _get_password_manager()

    # Check if user exists
    user_info = password_manager.get_user_info(username)
    if user_info is None:
        click.echo(f"User '{username}' not found. Use 'init-user' first.")
        return

    # Handle password input
    if password is None:
        password = getpass.getpass(f"Enter {service} password for {username}: ")

    # Set service password
    password_manager.set_service_password(username, service, password)
    click.echo(f"Set {service} password for user: {username}")


@passwords.command("get-service")
@click.option("--username", required=True, help="Username")
@click.option("--service", required=True, help="Service name")
@click.option("--show-password", is_flag=True, help="Show the actual password")
def get_service_password(username: str, service: str, show_password: bool) -> None:
    """Get service password for a user (for integration scripts)."""
    password_manager = _get_password_manager()

    service_password = password_manager.get_user_password_for_service(username, service)

    if service_password is None:
        click.echo(
            "auto"
        )  # Used by startup scripts to know they should derive password
    elif show_password:
        click.echo(service_password)
    else:
        click.echo("****** (use --show-password to reveal)")


@passwords.command("list")
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def list_users(format: str) -> None:
    """List users and password status."""
    password_manager = _get_password_manager()
    users = password_manager.list_users()

    if format == "json":
        click.echo(json.dumps(users, indent=2))
        return

    if not users:
        click.echo("No users found in secrets.")
        return

    # Table format
    click.echo(
        f"{'Username':<15} {'Created':<20} "  # noqa: E231
        f"{'Last Changed':<20} {'Services':<20}"  # noqa: E231
    )
    click.echo("-" * 80)

    for username, info in users.items():
        if info is not None:
            services = (
                ", ".join(info["service_overrides"])
                if info["service_overrides"]
                else "none"
            )
            click.echo(
                f"{username:<15} {info['created_at'][:19]:<20} "  # noqa: E231
                f"{info['last_changed'][:19]:<20} {services:<20}"  # noqa: E231
            )


@passwords.command("info")
@click.option("--username", required=True, help="Username to show info for")
def user_info(username: str) -> None:
    """Show detailed password information for a user."""
    password_manager = _get_password_manager()
    info = password_manager.get_user_info(username)

    if info is None:
        click.echo(f"User '{username}' not found in secrets.")
        return

    click.echo(f"User: {username}")
    click.echo(f"Created: {info['created_at']}")
    click.echo(f"Last Changed: {info['last_changed']}")
    click.echo(
        f"WebDAV Override: {'Yes' if info['has_webdav_override'] else 'No (auto)'}"
    )
    click.echo(
        f"Email Override: {'Yes' if info['has_email_override'] else 'No (auto)'}"
    )

    if info["service_overrides"]:
        click.echo("Service Overrides:")
        for service in info["service_overrides"]:
            click.echo(f"  - {service}")
    else:
        click.echo("Service Overrides: None")


@passwords.command("verify")
@click.option("--username", required=True, help="Username to verify")
@click.option("--password", help="Password to verify (will prompt if not provided)")
def verify_password(username: str, password: Optional[str]) -> None:
    """Verify a user's password."""
    password_manager = _get_password_manager()

    if password is None:
        password = getpass.getpass(f"Enter password for {username}: ")

    if password_manager.verify_user_password(username, password):
        click.echo("Password is correct!")
    else:
        click.echo("Password is incorrect!")


@passwords.command("rotate-all")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def rotate_all_passwords(confirm: bool) -> None:
    """Rotate passwords for all users."""
    if confirm is False:
        click.echo("This will generate new passwords for ALL users!")
        if click.confirm("Are you sure you want to continue?") is False:
            return

    password_manager = _get_password_manager()
    new_passwords = password_manager.rotate_all_passwords()

    click.echo("New passwords generated:")
    for username, password in new_passwords.items():
        click.echo(f"  {username}: {password}")

    click.echo("\nPlease save these passwords securely!")


@passwords.command("delete")
@click.option("--username", required=True, help="Username to delete")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def delete_user(username: str, confirm: bool) -> None:
    """Delete user secrets."""
    if confirm is False:
        if click.confirm(f"Delete all secrets for user '{username}'?") is False:
            return

    password_manager = _get_password_manager()
    if password_manager.delete_user(username):
        click.echo(f"Deleted secrets for user: {username}")
    else:
        click.echo(f"User '{username}' not found in secrets.")


@passwords.command("export-service")
@click.option("--service", required=True, help="Service to export passwords for")
@click.option(
    "--show-passwords", is_flag=True, help="Show actual passwords (for scripts)"
)
def export_service_passwords(service: str, show_passwords: bool) -> None:
    """Export passwords for a service (for container integration)."""
    password_manager = _get_password_manager()
    passwords = password_manager.export_service_passwords(service)

    if show_passwords:
        for username, password in passwords.items():
            click.echo(f"{username}" + ":" + f"{password}")
    else:
        click.echo(f"Found {len(passwords)} users for service '{service}'")
        for username in passwords:
            click.echo(f"  {username}")
