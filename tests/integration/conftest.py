"""Pytest configuration and fixtures for integration tests."""

import subprocess
import time
from typing import Generator

import pytest

from net_servers.actions.container import ContainerManager
from net_servers.config.containers import get_container_config


class ContainerTestHelper:
    """Helper class for container integration testing."""

    def __init__(self, config_name: str):
        """Initialize container test helper.

        Args:
            config_name: Name of the container configuration to use
        """
        self.config_name = config_name
        self.config = get_container_config(config_name)
        self.manager = ContainerManager(self.config)

    def start_container(self, port_mapping: str = None) -> bool:
        """Start the container and wait for it to be ready."""
        # Stop any existing container first
        self.manager.stop()
        self.manager.remove_container(force=True)

        # Start the container
        result = self.manager.run(detached=True, port_mapping=port_mapping)
        if not result.success:
            return False

        # Wait for container to be ready
        max_attempts = 60  # Increased timeout for mail server
        for _ in range(max_attempts):
            if self.is_container_ready():
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

    def get_container_port(self, internal_port: int) -> int:
        """Get the host port mapped to the container's internal port."""
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
    """Session-scoped fixture for Apache container testing."""
    if not podman_available:
        pytest.skip("Podman not available for integration testing")

    helper = ContainerTestHelper("apache")

    # Start container with port mapping
    if not helper.start_container(port_mapping="8080:80"):
        pytest.fail("Failed to start Apache container")

    try:
        yield helper
        # Print debugging info when tests complete
        helper.print_container_info()
        print(
            "\nApache container left running for debugging. "
            "Clean up manually when done."
        )
    except Exception:
        # On test failures, keep container for debugging
        helper.print_container_info()
        print("\nApache container left running for debugging failed tests.")
        raise
    # Note: Container is intentionally NOT stopped to allow log inspection


@pytest.fixture(scope="session")
def mail_container(
    podman_available: bool,
) -> Generator[ContainerTestHelper, None, None]:
    """Session-scoped fixture for Mail container testing."""
    if not podman_available:
        pytest.skip("Podman not available for integration testing")

    helper = ContainerTestHelper("mail")

    # Use fixed ports for session-scoped container to avoid conflicts
    port_mapping = "25025:25,25143:143,25110:110"
    if not helper.start_container(port_mapping=port_mapping):
        pytest.fail("Failed to start Mail container")

    # Give mail services extra time to initialize
    time.sleep(10)

    try:
        yield helper
        # Print debugging info when tests complete
        helper.print_container_info()
        print(
            "\nMail container left running for debugging. Clean up manually when done."
        )
    except Exception:
        # On test failures, keep container for debugging
        helper.print_container_info()
        print("\nMail container left running for debugging failed tests.")
        raise
    # Note: Container is intentionally NOT stopped to allow log inspection
