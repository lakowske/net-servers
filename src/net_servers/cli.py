"""Command-line interface for container management."""

import json
import logging
import sys
from typing import List, Optional

import click

from net_servers.actions.container import ContainerManager
from net_servers.cli_config import config
from net_servers.config.containers import get_container_config, list_container_configs


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def _display_service_info(container_config, port_mapping: Optional[str] = None) -> None:
    """Display port mappings and service URLs for a started container."""
    click.echo("Port Mappings:")

    # Handle custom port mapping
    if port_mapping:
        host_port, container_port = port_mapping.split(":")
        click.echo(f"  {host_port} -> {container_port}")

        # Generate service URL based on container type
        service_name = _get_service_name(container_config.image_name)
        if service_name == "apache":
            click.echo("Service URLs:")
            click.echo("  HTTP: http://localhost" + ":" + f"{host_port}")
            if container_port == "443":
                click.echo("  HTTPS: https://localhost" + ":" + f"{host_port}")
        return

    # Display configured port mappings
    if container_config.port_mappings:
        for mapping in container_config.port_mappings:
            protocol_suffix = (
                f"/{mapping.protocol}" if mapping.protocol != "tcp" else ""
            )
            click.echo(
                f"  {mapping.host_port} -> {mapping.container_port}{protocol_suffix}"
            )

        # Generate service URLs
        service_name = _get_service_name(container_config.image_name)
        service_urls = _generate_service_urls(
            service_name, container_config.port_mappings
        )
        if service_urls:
            click.echo("Service URLs:")
            for url in service_urls:
                click.echo(f"  {url}")
    else:
        # Fallback to legacy single port display
        click.echo(f"  {container_config.port} -> (container port)")


def _get_service_name(image_name: str) -> str:
    """Extract service name from image name."""
    if "apache" in image_name:
        return "apache"
    elif "mail" in image_name:
        return "mail"
    elif "dns" in image_name:
        return "dns"
    return "unknown"


def _generate_service_urls(service_name: str, port_mappings) -> List[str]:
    """Generate service URLs based on service type and port mappings."""
    urls = []

    if service_name == "apache":
        for mapping in port_mappings:
            if mapping.container_port == 80:
                urls.append("HTTP: http://localhost" + ":" + f"{mapping.host_port}")
            elif mapping.container_port == 443:
                urls.append("HTTPS: https://localhost" + ":" + f"{mapping.host_port}")

    elif service_name == "mail":
        for mapping in port_mappings:
            if mapping.container_port == 25:
                urls.append("SMTP: localhost" + ":" + f"{mapping.host_port}")
            elif mapping.container_port == 143:
                urls.append("IMAP: localhost" + ":" + f"{mapping.host_port}")
            elif mapping.container_port == 110:
                urls.append("POP3: localhost" + ":" + f"{mapping.host_port}")
            elif mapping.container_port == 993:
                urls.append("IMAPS: localhost" + ":" + f"{mapping.host_port}")
            elif mapping.container_port == 995:
                urls.append("POP3S: localhost" + ":" + f"{mapping.host_port}")
            elif mapping.container_port == 587:
                urls.append("SMTP-TLS: localhost" + ":" + f"{mapping.host_port}")

    elif service_name == "dns":
        for mapping in port_mappings:
            if mapping.container_port == 53:
                urls.append(
                    "DNS: localhost" + ":" + f"{mapping.host_port} ({mapping.protocol})"
                )

    return urls


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    """Net-servers management commands."""
    setup_logging(verbose)


@cli.group()
def container() -> None:
    """Container management commands."""
    pass


@container.command()
@click.option("--config", "-c", required=True, help="Config name (apache, mail)")
@click.option("--image-name", help="Override image name")
@click.option("--dockerfile", help="Override dockerfile path")
@click.option("--rebuild", is_flag=True, help="Force rebuild (no cache)")
def build(
    config: str,
    image_name: Optional[str],
    dockerfile: Optional[str],
    rebuild: bool,
) -> None:
    """Build container image."""
    try:
        container_config = get_container_config(config, use_config_manager=False)

        # Apply overrides
        if image_name:
            container_config.image_name = image_name
        if dockerfile:
            container_config.dockerfile = dockerfile

        manager = ContainerManager(container_config)
        result = manager.build(rebuild=rebuild)

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            click.echo(f"Build failed with return code {result.return_code}", err=True)
            sys.exit(result.return_code)

        click.echo(f"Successfully built {container_config.image_name}")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@container.command()
@click.option("--config", "-c", required=True, help="Config name (apache, mail)")
@click.option("--port", "-p", type=int, help="Override port mapping (host port)")
@click.option("--detached/--interactive", default=True, help="Run in detached mode")
@click.option("--port-mapping", help="Custom port mapping (e.g., '8080:80')")
def run(
    config: str,
    port: Optional[int],
    detached: bool,
    port_mapping: Optional[str],
) -> None:
    """Run container."""
    try:
        container_config = get_container_config(config, use_config_manager=True)

        # Apply port override
        if port:
            container_config.port = port

        manager = ContainerManager(container_config)
        result = manager.run(detached=detached, port_mapping=port_mapping)

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            click.echo(f"Run failed with return code {result.return_code}", err=True)
            sys.exit(result.return_code)

        if detached:
            click.echo(f"Container {container_config.container_name} started")
            _display_service_info(container_config, port_mapping)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@container.command()
@click.option("--config", "-c", required=True, help="Config name (apache, mail)")
def stop(config: str) -> None:
    """Stop running container."""
    try:
        container_config = get_container_config(config, use_config_manager=True)
        manager = ContainerManager(container_config)
        result = manager.stop()

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            click.echo(f"Stop failed with return code {result.return_code}", err=True)
            sys.exit(result.return_code)

        click.echo(f"Container {container_config.container_name} stopped")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@container.command()
@click.option("--config", "-c", required=True, help="Config name (apache, mail)")
@click.option("--force", "-f", is_flag=True, help="Force remove")
def remove(config: str, force: bool) -> None:
    """Remove container."""
    try:
        container_config = get_container_config(config, use_config_manager=True)
        manager = ContainerManager(container_config)
        result = manager.remove_container(force=force)

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            click.echo(f"Remove failed with return code {result.return_code}", err=True)
            sys.exit(result.return_code)

        click.echo(f"Container {container_config.container_name} removed")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@container.command()
@click.option("--config", "-c", required=True, help="Config name (apache, mail)")
@click.option("--force", "-f", is_flag=True, help="Force remove")
def remove_image(config: str, force: bool) -> None:
    """Remove container image."""
    try:
        container_config = get_container_config(config, use_config_manager=False)
        manager = ContainerManager(container_config)
        result = manager.remove_image(force=force)

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            click.echo(
                f"Remove image failed with return code {result.return_code}", err=True
            )
            sys.exit(result.return_code)

        click.echo(f"Image {container_config.image_name} removed")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@container.command()
@click.option("--all", "-a", is_flag=True, help="Show all containers")
def list_containers(all: bool) -> None:
    """List containers."""
    # Use apache config as default for listing (doesn't matter which)
    container_config = get_container_config("apache")
    manager = ContainerManager(container_config)
    result = manager.list_containers(all_containers=all)

    if result.stdout:
        try:
            # Try to format JSON output nicely
            data = json.loads(result.stdout)
            click.echo(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            # Fallback to raw output
            click.echo(result.stdout)
    if result.stderr:
        click.echo(result.stderr, err=True)

    if not result.success:
        click.echo(f"List failed with return code {result.return_code}", err=True)
        sys.exit(result.return_code)


@container.command()
@click.option("--config", "-c", required=True, help="Config name (apache, mail)")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--tail", type=int, help="Number of lines to show from end of logs")
def logs(config: str, follow: bool, tail: Optional[int]) -> None:
    """Show container logs."""
    try:
        container_config = get_container_config(config, use_config_manager=True)
        manager = ContainerManager(container_config)
        result = manager.logs(follow=follow, tail=tail)

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            click.echo(f"Logs failed with return code {result.return_code}", err=True)
            sys.exit(result.return_code)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@container.command("build-all")
@click.option("--rebuild", is_flag=True, help="Force rebuild (no cache)")
def build_all(rebuild: bool) -> None:
    """Build all container images."""
    configs = list_container_configs()
    failed = []

    for name, _ in configs.items():
        click.echo(f"Building {name}...")
        container_config = get_container_config(name, use_config_manager=False)
        manager = ContainerManager(container_config)
        result = manager.build(rebuild=rebuild)

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            failed.append(name)
            click.echo(f"Failed to build {name}", err=True)
        else:
            click.echo(f"Successfully built {container_config.image_name}")

    if failed:
        click.echo(f"Failed to build: {', '.join(failed)}", err=True)
        sys.exit(1)


@container.command("start-all")
@click.option("--detached/--interactive", default=True, help="Run in detached mode")
def start_all(detached: bool) -> None:
    """Start all containers."""
    configs = list_container_configs()
    failed = []

    for name, _ in configs.items():
        click.echo(f"Starting {name}...")
        container_config = get_container_config(name, use_config_manager=True)
        manager = ContainerManager(container_config)
        result = manager.run(detached=detached)

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            failed.append(name)
            click.echo(f"Failed to start {name}", err=True)
        else:
            click.echo(f"Container {container_config.container_name} started")
            _display_service_info(container_config)

    if failed:
        click.echo(f"Failed to start: {', '.join(failed)}", err=True)
        sys.exit(1)


@container.command("stop-all")
def stop_all() -> None:
    """Stop all containers."""
    configs = list_container_configs()
    failed = []

    for name, _ in configs.items():
        click.echo(f"Stopping {name}...")
        container_config = get_container_config(name, use_config_manager=True)
        manager = ContainerManager(container_config)
        result = manager.stop()

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            failed.append(name)
            click.echo(f"Failed to stop {name}", err=True)
        else:
            click.echo(f"Container {container_config.container_name} stopped")

    if failed:
        click.echo(f"Failed to stop: {', '.join(failed)}", err=True)


@container.command("remove-all")
@click.option("--force", "-f", is_flag=True, help="Force remove")
def remove_all(force: bool) -> None:
    """Remove all containers."""
    configs = list_container_configs()
    failed = []

    for name, _ in configs.items():
        click.echo(f"Removing container {name}...")
        container_config = get_container_config(name, use_config_manager=True)
        manager = ContainerManager(container_config)
        result = manager.remove_container(force=force)

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            failed.append(name)
            click.echo(f"Failed to remove container {name}", err=True)
        else:
            click.echo(f"Container {container_config.container_name} removed")

    if failed:
        click.echo(f"Failed to remove containers: {', '.join(failed)}", err=True)


@container.command("remove-all-images")
@click.option("--force", "-f", is_flag=True, help="Force remove")
def remove_all_images(force: bool) -> None:
    """Remove all container images."""
    configs = list_container_configs()
    failed = []

    for name, _ in configs.items():
        click.echo(f"Removing image {name}...")
        container_config = get_container_config(name, use_config_manager=False)
        manager = ContainerManager(container_config)
        result = manager.remove_image(force=force)

        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if not result.success:
            failed.append(name)
            click.echo(f"Failed to remove image {name}", err=True)
        else:
            click.echo(f"Image {container_config.image_name} removed")

    if failed:
        click.echo(f"Failed to remove images: {', '.join(failed)}", err=True)


@container.command("clean-all")
@click.option("--force", "-f", is_flag=True, help="Force remove")
def clean_all(force: bool) -> None:
    """Stop all containers, remove containers, and remove images."""
    click.echo("Cleaning all containers and images...")

    # Stop all containers first
    click.echo("Stopping all containers...")
    configs = list_container_configs()
    for name in configs.keys():
        container_config = get_container_config(name, use_config_manager=True)
        manager = ContainerManager(container_config)
        result = manager.stop()
        if result.success:
            click.echo(f"Stopped {container_config.container_name}")

    # Remove all containers
    click.echo("Removing all containers...")
    for name in configs.keys():
        container_config = get_container_config(name, use_config_manager=True)
        manager = ContainerManager(container_config)
        result = manager.remove_container(force=force)
        if result.success:
            click.echo(f"Removed container {container_config.container_name}")

    # Remove all images
    click.echo("Removing all images...")
    for name in configs.keys():
        container_config = get_container_config(name, use_config_manager=False)
        manager = ContainerManager(container_config)
        result = manager.remove_image(force=force)
        if result.success:
            click.echo(f"Removed image {container_config.image_name}")

    click.echo("Clean complete!")


@container.command("list-configs")
def list_configs() -> None:
    """List available container configurations."""
    configs = list_container_configs()

    click.echo("Available container configurations:")
    for name, container_config in configs.items():
        click.echo(f"  {name}" + ":")
        click.echo(f"    image: {container_config.image_name}")
        click.echo(f"    dockerfile: {container_config.dockerfile}")
        click.echo(f"    port: {container_config.port}")
        click.echo(f"    container_name: {container_config.container_name}")


@container.command("test")
@click.option(
    "--config",
    "-c",
    help="Config name to test (apache, mail). If not specified, tests all containers",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose test output")
@click.option("--build", "-b", is_flag=True, help="Build containers before testing")
@click.option(
    "--include-ssl",
    is_flag=True,
    help="Include SSL/TLS tests (may fail without proper setup)",
)
def test_integration(
    config: Optional[str], verbose: bool, build: bool, include_ssl: bool
) -> None:
    """Run integration tests for container services."""
    import subprocess

    # Show current environment info
    try:
        from net_servers.cli_environments import _get_config_manager

        config_manager = _get_config_manager()
        current_env = config_manager.get_current_environment()
        click.echo(f"Running integration tests in environment: {current_env.name}")
    except Exception:
        click.echo("Running integration tests in current environment")

    # Check if pytest is available
    try:
        subprocess.run(  # nosec B607
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo("Error: pytest is required for integration tests", err=True)
        click.echo("Install with: pip install pytest requests", err=True)
        sys.exit(1)

    # Check if podman is available
    try:
        subprocess.run(
            ["/usr/bin/podman", "--version"], capture_output=True, check=True
        )  # nosec B607
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            # Fallback to podman in PATH
            subprocess.run(
                ["podman", "--version"], capture_output=True, check=True
            )  # nosec B607
        except (subprocess.CalledProcessError, FileNotFoundError):
            click.echo("Error: podman is required for integration tests", err=True)
            click.echo(
                "Please install podman to run container integration tests", err=True
            )
            sys.exit(1)

    if build:
        click.echo("Building containers before testing...")
        if config:
            # Build specific container
            container_config = get_container_config(config, use_config_manager=False)
            manager = ContainerManager(container_config)
            result = manager.build()
            if not result.success:
                click.echo(f"Failed to build {config} container", err=True)
                sys.exit(1)
            click.echo(f"Successfully built {config} container")
        else:
            # Build all containers
            configs = list_container_configs()
            for name, _ in configs.items():
                container_config = get_container_config(name, use_config_manager=False)
                manager = ContainerManager(container_config)
                result = manager.build()
                if not result.success:
                    click.echo(f"Failed to build {name} container", err=True)
                    sys.exit(1)
                click.echo(f"Successfully built {name} container")

    # Run integration tests
    test_args = [sys.executable, "-m", "pytest"]

    if config:
        # Test specific container
        test_args.append(f"tests/integration/test_{config}.py")
    else:
        # Test all containers
        test_args.append("tests/integration/")

    if verbose:
        test_args.extend(["-v", "-s"])

    # Exclude SSL tests by default unless explicitly requested
    if not include_ssl:
        test_args.extend(["-k", "not test_ssl_tls"])

    click.echo("Running integration tests...")
    if not include_ssl:
        click.echo(
            "Note: SSL/TLS tests excluded by default. "
            "Use --include-ssl to include them."
        )
    click.echo(f"Command: {' '.join(test_args)}")

    result = subprocess.run(test_args)
    sys.exit(result.returncode)


# Add configuration commands to main CLI
cli.add_command(config)

# Add certificate commands to main CLI
from net_servers.cli_certificates import certificates  # noqa: E402

cli.add_command(certificates)

# Add environment commands to main CLI
from net_servers.cli_environments import environments  # noqa: E402

cli.add_command(environments)

# Add password commands to main CLI
from net_servers.cli_passwords import passwords  # noqa: E402

cli.add_command(passwords)


if __name__ == "__main__":
    cli()
