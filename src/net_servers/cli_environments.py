"""Environment management CLI commands."""

import os
import sys
from pathlib import Path
from typing import List

import click

from net_servers.config.manager import ConfigurationManager
from net_servers.config.schemas import EnvironmentsConfig


def _get_environments_config_path() -> str:
    """Get the path to environments.yaml file.

    Priority:
    1. Environment variable NET_SERVERS_CONFIG
    2. ./environments.yaml (project workspace default)
    3. /data/environments.yaml (container environment)
    """
    # Check environment variable first
    config_path = os.environ.get("NET_SERVERS_CONFIG")
    if config_path and os.path.exists(config_path):
        return config_path

    # Container environment
    if os.path.exists("/data"):
        container_config = "/data/environments.yaml"
        if os.path.exists(container_config):
            return container_config

    # Default to project workspace
    return os.path.abspath("./environments.yaml")


def _get_environments_base_path() -> str:
    """Get the base path for environment directories.

    Priority:
    1. Environment variable NET_SERVERS_ENVIRONMENTS_DIR
    2. ./environments (project workspace default)
    3. /data/environments (container environment)
    """
    # Check environment variable first
    base_path = os.environ.get("NET_SERVERS_ENVIRONMENTS_DIR")
    if base_path:
        return os.path.abspath(base_path)

    # Container environment (only if we can write to /data)
    if os.path.exists("/data") and os.access("/data", os.W_OK):
        return "/data/environments"

    # Default to project workspace
    return os.path.abspath("./environments")


def _get_config_manager() -> ConfigurationManager:
    """Get configuration manager for the current environment."""
    # Get environments configuration file path
    env_config_file = Path(_get_environments_config_path())
    env_config_path = str(env_config_file)

    if not env_config_file.exists():
        raise FileNotFoundError(
            f"Environments configuration not found at {env_config_file}. "
            f"Initialize environments with: python -m net_servers.cli environments init"
        )

    # Load environments config to get current environment
    from net_servers.config.schemas import EnvironmentsConfig, load_yaml_config

    env_config = load_yaml_config(env_config_file, EnvironmentsConfig)

    # Find current environment
    current_env_name = env_config.current_environment
    current_env = None
    for env in env_config.environments:
        if env.name == current_env_name:
            current_env = env
            break

    if current_env is None:
        available_envs = [e.name for e in env_config.environments]
        raise ValueError(
            f"Current environment '{current_env_name}' not found in "  # noqa: E713
            f"environments configuration. Available environments: {available_envs}"
        )

    # Return ConfigurationManager for current environment
    return ConfigurationManager(
        current_env.base_path, environments_config_path=env_config_path
    )


def _get_environments_config() -> tuple[str, EnvironmentsConfig]:
    """Load environments configuration."""
    env_config_file = Path(_get_environments_config_path())

    from net_servers.config.schemas import EnvironmentsConfig, load_yaml_config

    env_config = load_yaml_config(env_config_file, EnvironmentsConfig)
    return str(env_config_file), env_config


def _save_environments_config(env_config: EnvironmentsConfig) -> None:
    """Save environments configuration."""
    env_config_file = Path(_get_environments_config_path())

    from net_servers.config.schemas import save_yaml_config

    save_yaml_config(env_config, env_config_file)


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
        _, env_config = _get_environments_config()
        environments = env_config.environments
        current_env = env_config.current_environment

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
        click.echo(f"Certificate Mode: {current_env.certificate_mode}")
        click.echo(f"Tags: {', '.join(current_env.tags)}")
        click.echo(f"Enabled: {'Yes' if current_env.enabled else 'No'}")
        click.echo(f"Created: {current_env.created_at}")
        click.echo(f"Last Used: {current_env.last_used}")

    except Exception as e:
        click.echo(f"Error getting current environment: {e}", err=True)
        sys.exit(1)


@environments.command("switch")
@click.argument("name")
@click.option(
    "--provision-certs",
    is_flag=True,
    help="Automatically provision certificates for the environment",
)
def switch_environment(name: str, provision_certs: bool) -> None:
    """Switch to a different environment."""
    try:
        # Load environments config
        _, env_config = _get_environments_config()

        # Find target environment
        target_env = None
        for env in env_config.environments:
            if env.name == name:
                target_env = env
                break

        if not target_env:
            raise ValueError(f"Environment '{name}' not found")

        if not target_env.enabled:
            raise ValueError(f"Environment '{name}' is disabled")

        # Update current environment and last used timestamp
        from datetime import datetime

        target_env.last_used = datetime.now().isoformat()
        env_config.current_environment = name

        # Save updated config
        _save_environments_config(env_config)

        # Ensure environment directory structure exists
        from net_servers.config.schemas import ConfigurationPaths

        env_paths = ConfigurationPaths(base_path=Path(target_env.base_path))
        env_paths.ensure_directories()

        click.echo(
            f"Switched to environment '{target_env.name}' at {target_env.base_path}"
        )

        # Optionally provision certificates
        if provision_certs:
            click.echo(
                f"Provisioning certificates for environment "
                f"'{target_env.name}' using mode '{target_env.certificate_mode}'..."
            )
            try:
                # Create environment-specific config manager
                env_config_manager = ConfigurationManager(target_env.base_path)
                success = env_config_manager.provision_certificates(
                    domain=target_env.domain,
                    admin_email=target_env.admin_email,
                    certificate_mode=target_env.certificate_mode,
                    force=False,
                )
                if success:
                    click.echo("✅ Certificates ready for environment")
                else:
                    click.echo("⚠️  Certificate provisioning failed")
            except Exception as e:
                click.echo(f"⚠️  Certificate provisioning error: {e}")

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
    "--certificate-mode",
    type=click.Choice(["self_signed", "le_staging", "le_production"]),
    default="self_signed",
    help="Default certificate mode for environment",
)
@click.option(
    "--tag", "-t", multiple=True, help="Environment tags (can be used multiple times)"
)
def add_environment(
    name: str,
    description: str,
    base_path: str,
    domain: str,
    admin_email: str,
    certificate_mode: str,
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
            certificate_mode=certificate_mode,
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
        _, env_config = _get_environments_config()

        # Find environment
        target_env = None
        for env in env_config.environments:
            if env.name == name:
                target_env = env
                break

        if not target_env:
            raise ValueError(f"Environment '{name}' not found")

        # Enable environment
        target_env.enabled = True
        _save_environments_config(env_config)

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
        click.echo(f"Certificate Mode: {env.certificate_mode}")
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
@click.option(
    "--provision-certs",
    is_flag=True,
    help="Automatically provision certificates for development environment",
)
@click.option(
    "--config-file",
    help="Path to environments.yaml file (default: ./environments.yaml)",
)
@click.option(
    "--environments-dir",
    help="Base directory for environment directories (default: ./environments)",
)
def init_environments(
    force: bool, provision_certs: bool, config_file: str, environments_dir: str
) -> None:
    """Initialize environments configuration with defaults."""
    try:
        # Determine paths
        if config_file:
            env_config_path = Path(config_file).resolve()
        else:
            env_config_path = Path(_get_environments_config_path())

        if environments_dir:
            environments_base = Path(environments_dir).resolve()
        else:
            environments_base = Path(_get_environments_base_path())

        # Check if environments.yaml already exists
        if env_config_path.exists() and not force:
            click.echo(
                f"Environments configuration already exists at {env_config_path}"
            )
            click.echo("Use --force to reinitialize.")
            return

        # Create parent directory for config file if needed
        env_config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create environments configuration
        from datetime import datetime

        from net_servers.config.schemas import EnvironmentConfig, EnvironmentsConfig

        now = datetime.now().isoformat()
        default_environments = EnvironmentsConfig(
            current_environment="development",
            environments=[
                EnvironmentConfig(
                    name="development",
                    description="Development environment for local testing",
                    base_path=str(environments_base / "development"),
                    domain="local.dev",
                    admin_email="admin@local.dev",
                    tags=["development", "local"],
                    created_at=now,
                    last_used=now,
                    certificate_mode="self_signed",
                ),
                EnvironmentConfig(
                    name="staging",
                    description="Staging environment for pre-production testing",
                    base_path=str(environments_base / "staging"),
                    domain="staging.local.dev",
                    admin_email="admin@local.dev",
                    tags=["staging", "testing"],
                    created_at=now,
                    last_used=now,
                    enabled=False,
                    certificate_mode="le_staging",
                ),
                EnvironmentConfig(
                    name="testing",
                    description="Testing environment for integration tests",
                    base_path=str(environments_base / "testing"),
                    domain="testing.local.dev",
                    admin_email="admin@local.dev",
                    tags=["testing", "integration", "ci-cd"],
                    created_at=now,
                    last_used=now,
                    enabled=False,
                    certificate_mode="self_signed",
                ),
                EnvironmentConfig(
                    name="production",
                    description="Production environment for live services",
                    base_path=str(environments_base / "production"),
                    domain="example.com",
                    admin_email="admin@local.dev",
                    tags=["production", "live"],
                    created_at=now,
                    last_used=now,
                    enabled=False,
                    certificate_mode="le_production",
                ),
            ],
        )

        # Save environments config
        from net_servers.config.schemas import save_yaml_config

        save_yaml_config(default_environments, env_config_path)

        click.echo(f"✅ Created environments configuration at {env_config_path}")
        click.echo(f"✅ Environment directories will be created in {environments_base}")

        # Create directory structure for all environments
        from net_servers.config.schemas import ConfigurationPaths

        for env in default_environments.environments:
            env_paths = ConfigurationPaths(base_path=Path(env.base_path))
            env_paths.ensure_directories()

        # Initialize the current environment's configuration files
        # Create a manager specifically for the development environment
        dev_env = next(
            env
            for env in default_environments.environments
            if env.name == "development"
        )
        from net_servers.config.manager import ConfigurationManager

        # Create environment-specific configuration manager
        env_config_manager = ConfigurationManager(dev_env.base_path)
        env_config_manager.initialize_default_configs()

        # Optionally provision certificates for the development environment
        if provision_certs:
            click.echo(
                "Provisioning default certificates for development environment..."
            )
            try:
                # Use the environment-specific config manager for certificate operations
                success = env_config_manager.provision_certificates(
                    domain=dev_env.domain,
                    admin_email=dev_env.admin_email,
                    certificate_mode=dev_env.certificate_mode,
                    force=False,
                )
                if success:
                    click.echo("✅ Certificates provisioned for development environment")
                else:
                    click.echo(
                        "⚠️  Certificate provisioning failed for development "
                        "environment"
                    )
            except Exception as e:
                click.echo(f"⚠️  Certificate provisioning error: {e}")
        else:
            click.echo(
                "💡 Use --provision-certs to automatically provision certificates"
            )

        click.echo("Initialized environments configuration with defaults:")

        # Show created environments
        for env in default_environments.environments:
            status = (
                "current"
                if env.name == default_environments.current_environment
                else "available"
            )
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
