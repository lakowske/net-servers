"""Environment management CLI commands."""

import os
import sys
from pathlib import Path
from typing import List

import click

from net_servers.config.manager import ConfigurationManager


def _get_config_manager() -> ConfigurationManager:
    """Get configuration manager with proper base path detection."""
    base_path = (
        "/data" if os.path.exists("/data") else os.path.expanduser("~/.net-servers")
    )
    return ConfigurationManager(base_path)


@click.group()
def environments() -> None:
    """Environment management commands."""
    pass


@environments.command("list")
@click.option("--current-only", is_flag=True, help="Show only the current environment")
@click.option("--enabled-only", is_flag=True, help="Show only enabled environments")
@click.option("--format", type=click.Choice(["table", "json"]), default="table")
def list_environments(current_only: bool, enabled_only: bool, format: str) -> None:
    """List all environments."""
    try:
        config_manager = _get_config_manager()
        environments = config_manager.list_environments()
        current_env = config_manager.environments_config.current_environment

        if current_only:
            environments = [env for env in environments if env.name == current_env]
        elif enabled_only:
            environments = [env for env in environments if env.enabled]

        if format == "json":
            import json

            env_data = []
            for env in environments:
                env_dict = env.model_dump()
                env_dict["is_current"] = env.name == current_env
                env_data.append(env_dict)
            click.echo(json.dumps(env_data, indent=2))
        else:
            # Table format
            if not environments:
                click.echo("No environments found.")
                return

            click.echo("Environments:")
            click.echo("-" * 80)
            header = "Name".ljust(15) + " " + "Current".ljust(8) + " "
            header += "Enabled".ljust(8) + " " + "Domain".ljust(20) + " "
            header += "Description"
            click.echo(header)
            click.echo("-" * 80)

            for env in environments:
                current_marker = "✓" if env.name == current_env else ""
                enabled_marker = "✓" if env.enabled else "✗"
                row = env.name.ljust(15) + " " + current_marker.ljust(8) + " "
                row += enabled_marker.ljust(8) + " " + env.domain.ljust(20) + " "
                row += env.description
                click.echo(row)

    except Exception as e:
        click.echo(f"Error listing environments: {e}", err=True)
        sys.exit(1)


@environments.command("current")
def show_current() -> None:
    """Show the current environment."""
    try:
        config_manager = _get_config_manager()
        current_env = config_manager.get_current_environment()

        click.echo(f"Current Environment: {current_env.name}")
        click.echo(f"Description: {current_env.description}")
        click.echo(f"Domain: {current_env.domain}")
        click.echo(f"Base Path: {current_env.base_path}")
        click.echo(f"Admin Email: {current_env.admin_email}")
        click.echo(f"Tags: {', '.join(current_env.tags)}")
        click.echo(f"Enabled: {'Yes' if current_env.enabled else 'No'}")
        click.echo(f"Created: {current_env.created_at}")
        click.echo(f"Last Used: {current_env.last_used}")

    except Exception as e:
        click.echo(f"Error getting current environment: {e}", err=True)
        sys.exit(1)


@environments.command("switch")
@click.argument("name")
def switch_environment(name: str) -> None:
    """Switch to a different environment."""
    try:
        config_manager = _get_config_manager()
        env = config_manager.switch_environment(name)
        click.echo(f"Switched to environment '{env.name}' at {env.base_path}")

    except Exception as e:
        click.echo(f"Error switching environment: {e}", err=True)
        sys.exit(1)


@environments.command("add")
@click.argument("name")
@click.option("--description", "-d", required=True, help="Environment description")
@click.option("--base-path", "-p", required=True, help="Base path for environment data")
@click.option("--domain", required=True, help="Primary domain for environment")
@click.option("--admin-email", required=True, help="Admin email for environment")
@click.option(
    "--tag", "-t", multiple=True, help="Environment tags (can be used multiple times)"
)
def add_environment(
    name: str,
    description: str,
    base_path: str,
    domain: str,
    admin_email: str,
    tag: List[str],
) -> None:
    """Add a new environment."""
    try:
        config_manager = _get_config_manager()
        env = config_manager.add_environment(
            name=name,
            description=description,
            base_path=base_path,
            domain=domain,
            admin_email=admin_email,
            tags=list(tag),
        )
        click.echo(f"Created environment '{env.name}' at {env.base_path}")

    except Exception as e:
        click.echo(f"Error adding environment: {e}", err=True)
        sys.exit(1)


@environments.command("remove")
@click.argument("name")
@click.option("--force", is_flag=True, help="Force removal without confirmation")
def remove_environment(name: str, force: bool) -> None:
    """Remove an environment."""
    try:
        config_manager = _get_config_manager()

        if not force:
            env = config_manager.get_environment(name)
            if not env:
                click.echo(f"Environment '{name}' not found", err=True)
                sys.exit(1)

            click.echo(f"Environment: {env.name}")
            click.echo(f"Description: {env.description}")
            click.echo(f"Base Path: {env.base_path}")

            if not click.confirm("Are you sure you want to remove this environment?"):
                click.echo("Cancelled.")
                return

        config_manager.remove_environment(name)
        click.echo(f"Removed environment '{name}'")

    except Exception as e:
        click.echo(f"Error removing environment: {e}", err=True)
        sys.exit(1)


@environments.command("enable")
@click.argument("name")
def enable_environment(name: str) -> None:
    """Enable an environment."""
    try:
        config_manager = _get_config_manager()
        config_manager.enable_environment(name)
        click.echo(f"Enabled environment '{name}'")

    except Exception as e:
        click.echo(f"Error enabling environment: {e}", err=True)
        sys.exit(1)


@environments.command("disable")
@click.argument("name")
def disable_environment(name: str) -> None:
    """Disable an environment."""
    try:
        config_manager = _get_config_manager()
        config_manager.disable_environment(name)
        click.echo(f"Disabled environment '{name}'")

    except Exception as e:
        click.echo(f"Error disabling environment: {e}", err=True)
        sys.exit(1)


@environments.command("info")
@click.argument("name")
def show_environment_info(name: str) -> None:
    """Show detailed information about an environment."""
    try:
        config_manager = _get_config_manager()
        env = config_manager.get_environment(name)

        if not env:
            click.echo(f"Environment '{name}' not found", err=True)
            sys.exit(1)

        current_env = config_manager.environments_config.current_environment
        is_current = env.name == current_env

        click.echo(f"Environment: {env.name}")
        click.echo(f"Description: {env.description}")
        click.echo(f"Domain: {env.domain}")
        click.echo(f"Base Path: {env.base_path}")
        click.echo(f"Admin Email: {env.admin_email}")
        click.echo(f"Tags: {', '.join(env.tags) if env.tags else 'None'}")
        click.echo(f"Enabled: {'Yes' if env.enabled else 'No'}")
        click.echo(f"Current: {'Yes' if is_current else 'No'}")
        click.echo(f"Created: {env.created_at}")
        click.echo(f"Last Used: {env.last_used}")

        # Check if directory exists
        base_path = Path(env.base_path)
        click.echo(f"Directory Exists: {'Yes' if base_path.exists() else 'No'}")

        if base_path.exists():
            config_path = base_path / "config"
            state_path = base_path / "state"
            logs_path = base_path / "logs"

            click.echo("Directory Structure:")
            click.echo(
                f"  Config: {'✓' if config_path.exists() else '✗'} {config_path}"
            )
            click.echo(f"  State:  {'✓' if state_path.exists() else '✗'} {state_path}")
            click.echo(f"  Logs:   {'✓' if logs_path.exists() else '✗'} {logs_path}")

    except Exception as e:
        click.echo(f"Error getting environment info: {e}", err=True)
        sys.exit(1)


@environments.command("init")
@click.option(
    "--force", is_flag=True, help="Force initialization even if config exists"
)
def init_environments(force: bool) -> None:
    """Initialize environments configuration with defaults."""
    try:
        config_manager = _get_config_manager()

        # Check if environments.yaml already exists
        env_config_path = config_manager.paths.config_path / "environments.yaml"
        if env_config_path.exists() and not force:
            click.echo("Environments configuration already exists.")
            click.echo("Use --force to reinitialize.")
            return

        # Initialize with defaults
        config_manager.initialize_default_configs()
        click.echo("Initialized environments configuration with defaults:")

        # Show created environments
        environments = config_manager.list_environments()
        for env in environments:
            current_name = config_manager.environments_config.current_environment
            status = "current" if env.name == current_name else "available"
            click.echo(f"  - {env.name}: {env.description} ({status})")  # noqa: E221

    except Exception as e:
        click.echo(f"Error initializing environments: {e}", err=True)
        sys.exit(1)


@environments.command("validate")
def validate_environments() -> None:
    """Validate environments configuration."""
    try:
        config_manager = _get_config_manager()
        errors = config_manager.validate_configuration()

        if not errors:
            click.echo("✓ All environments configuration is valid")
            return

        click.echo("Configuration validation errors:")
        for error in errors:
            if "environment" in error.lower():
                click.echo(f"  ✗ {error}", err=True)

        # Show environment-specific issues
        env_errors = [e for e in errors if "environment" in e.lower()]
        if env_errors:
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error validating environments: {e}", err=True)
        sys.exit(1)
