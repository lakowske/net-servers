"""Pytest configuration and fixtures for integration tests."""

import subprocess
import time
from typing import Generator

import pytest

from net_servers.actions.container import ContainerManager
from net_servers.config.containers import get_container_config

from .port_manager import get_port_manager


class ContainerTestHelper:
    """Helper class for container integration testing."""

    def __init__(self, config_name: str, port_mapping: str = None):
        """Initialize container test helper.

        Args:
            config_name: Name of the container configuration to use
            port_mapping: Optional port mapping string, if None will use current
                environment ports
        """
        self.config_name = config_name
        # Use current environment for integration tests (auto-detected)
        self.config = get_container_config(config_name, environment_name=None)
        self.manager = ContainerManager(self.config)
        self.port_mapping = port_mapping

        # If no port mapping provided, use current environment ports
        if self.port_mapping is None:
            # Use the current environment port mappings directly
            if self.config.port_mappings:
                mapping_parts = []
                for pm in self.config.port_mappings:
                    mapping_parts.append(pm.to_podman_arg())
                self.port_mapping = ",".join(mapping_parts)
            else:
                # Fallback to dynamic allocation if no port mappings
                try:
                    self.port_mapping = get_port_manager().get_port_mapping_string(
                        config_name
                    )
                except ValueError:
                    # Service may not have predefined ports, that's OK
                    self.port_mapping = None

    def start_container(
        self, port_mapping: str = None, force_restart: bool = False
    ) -> bool:
        """Start the container and wait for it to be ready.

        Args:
            port_mapping: Optional port mapping string
            force_restart: If True, stop and restart existing container.
                          If False, reuse running container if available.
        """
        # Check if container is already running (unless force restart)
        if not force_restart and self.is_container_ready():
            print(f"Container {self.config.container_name} already running, reusing...")
            return True

        # Check if container exists but is not running
        container_exists = self._container_exists()

        # Only stop/remove if we need to restart or if container exists but is not ready
        if force_restart or (container_exists and not self.is_container_ready()):
            print(
                f"Stopping/removing existing container {self.config.container_name}..."
            )
            self.manager.stop()
            self.manager.remove_container(force=True)
        elif container_exists and self.is_container_ready():
            # Container exists and is running - this should have been caught above
            print(f"Container {self.config.container_name} is already running")
            return True

        # Use provided port mapping, or fall back to instance default
        actual_port_mapping = port_mapping or self.port_mapping

        # Start the container
        print(f"Starting container {self.config.container_name}...")
        result = self.manager.run(detached=True, port_mapping=actual_port_mapping)
        if not result.success:
            return False

        # Wait for container to be ready
        max_attempts = 60  # Increased timeout for mail server
        for _ in range(max_attempts):
            if self.is_container_ready():
                print(
                    f"Container {self.config.container_name} ready after {_+1} attempts"
                )
                return True
            time.sleep(1)

        return False

    def stop_container(self) -> None:
        """Stop and clean up the container."""
        self.manager.stop()
        self.manager.remove_container(force=True)

    def print_container_info(self) -> None:
        """Print container information for debugging."""
        print(f"\nContainer '{self.config.container_name}' is running.")
        print(f"To view logs: podman logs {self.config.container_name}")
        print(
            f"To exec into container: podman exec -it {self.config.container_name} bash"
        )
        print(f"To stop container: podman stop {self.config.container_name}")
        print(f"To remove container: podman rm -f {self.config.container_name}")

    def is_container_ready(self) -> bool:
        """Check if container is ready for testing."""
        try:
            # Check if container is running
            result = subprocess.run(
                [
                    "podman",
                    "ps",
                    "--filter",
                    f"name={self.config.container_name}",
                    "--format",
                    "{{.Status}}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0 and "Up" in result.stdout
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False

    def _container_exists(self) -> bool:
        """Check if container exists (running or stopped)."""
        try:
            result = subprocess.run(
                [
                    "podman",
                    "ps",
                    "-a",  # Show all containers, not just running
                    "--filter",
                    f"name={self.config.container_name}",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False

    def get_container_port(self, internal_port: int) -> int:
        """Get the host port mapped to the container's internal port."""
        # First try to get from current environment configuration
        for port_mapping in self.config.port_mappings:
            if port_mapping.container_port == internal_port:
                return port_mapping.host_port

        # Fall back to port manager if available
        try:
            port_manager = get_port_manager()
            return port_manager.get_host_port(self.config_name, internal_port)
        except (KeyError, ValueError):
            # Fall back to querying the container runtime
            pass

        try:
            result = subprocess.run(
                ["podman", "port", self.config.container_name, str(internal_port)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Output format: "0.0.0.0:8080"
                return int(result.stdout.strip().split(":")[-1])
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError):
            pass
        return internal_port

    def exec_command(self, command: list[str]) -> subprocess.CompletedProcess:
        """Execute a command inside the container."""
        cmd = ["podman", "exec", self.config.container_name] + command
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )


@pytest.fixture(scope="session")
def podman_available() -> bool:
    """Check if Podman is available for testing."""
    try:
        result = subprocess.run(
            ["podman", "--version"], capture_output=True, timeout=5, check=False
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return False


@pytest.fixture(scope="session")
def apache_container(
    podman_available: bool,
) -> Generator[ContainerTestHelper, None, None]:
    """Session-scoped fixture for Apache container testing.

    Container is started once per test session and reused across all tests.
    Container is left running after tests for debugging and performance.
    """
    if not podman_available:
        pytest.skip("Podman not available for integration testing")

    helper = ContainerTestHelper("apache")

    # Start container, reusing if already running
    if not helper.start_container(force_restart=False):
        pytest.fail("Failed to start Apache container")

    try:
        yield helper
        # Print debugging info when tests complete
        helper.print_container_info()
        print(
            "\nApache container left running for debugging and performance. "
            "Rerun tests to reuse existing container."
        )
    except Exception:
        # On test failures, keep container for debugging
        helper.print_container_info()
        print("\nApache container left running for debugging failed tests.")
        raise
    # Note: Container is intentionally NOT stopped to allow log inspection and reuse


@pytest.fixture(scope="session")
def mail_container(
    podman_available: bool,
) -> Generator[ContainerTestHelper, None, None]:
    """Session-scoped fixture for Mail container testing.

    Container is started once per test session and reused across all tests.
    Container is left running after tests for debugging and performance.
    """
    if not podman_available:
        pytest.skip("Podman not available for integration testing")

    helper = ContainerTestHelper("mail")

    # Start container, reusing if already running
    if not helper.start_container(force_restart=False):
        pytest.fail("Failed to start Mail container")

    # Give mail services extra time to initialize only if container was just started
    if not helper.is_container_ready():
        print("Waiting for mail services to initialize...")
        time.sleep(10)

    try:
        yield helper
        # Print debugging info when tests complete
        helper.print_container_info()
        print(
            "\nMail container left running for debugging and performance. "
            "Rerun tests to reuse existing container."
        )
    except Exception:
        # On test failures, keep container for debugging
        helper.print_container_info()
        print("\nMail container left running for debugging failed tests.")
        raise
    # Note: Container is intentionally NOT stopped to allow log inspection and reuse
