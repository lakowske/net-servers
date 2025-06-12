"""Tests for container management functionality."""

import subprocess
from unittest.mock import Mock, patch

import pytest

from net_servers.actions.container import (
    ContainerConfig,
    ContainerManager,
    ContainerResult,
)
from net_servers.config.containers import get_container_config


class TestContainerConfig:
    """Test ContainerConfig dataclass."""

    def test_container_config_defaults(self) -> None:
        """Test default values and auto-generation of container name."""
        config = ContainerConfig(image_name="test-image")

        assert config.image_name == "test-image"
        assert config.dockerfile == "Dockerfile"
        assert config.port == 8080
        assert config.container_name == "test-image"

    def test_container_config_with_registry(self) -> None:
        """Test container name generation from image with registry."""
        config = ContainerConfig(image_name="registry.io/org/test-image:latest")

        assert config.container_name == "test-image-latest"

    def test_container_config_explicit_name(self) -> None:
        """Test explicit container name is preserved."""
        config = ContainerConfig(image_name="test-image", container_name="custom-name")

        assert config.container_name == "custom-name"


class TestContainerResult:
    """Test ContainerResult dataclass."""

    def test_container_result_success(self) -> None:
        """Test successful result."""
        result = ContainerResult(
            success=True, stdout="output", stderr="", return_code=0
        )

        assert result.success
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.return_code == 0

    def test_container_result_failure(self) -> None:
        """Test failed result."""
        result = ContainerResult(
            success=False, stdout="", stderr="error message", return_code=1
        )

        assert not result.success
        assert result.stdout == ""
        assert result.stderr == "error message"
        assert result.return_code == 1


class TestContainerManager:
    """Test ContainerManager class."""

    @pytest.fixture
    def config(self) -> ContainerConfig:
        """Test container configuration."""
        return ContainerConfig(
            image_name="test-image",
            dockerfile="test.dockerfile",
            port=8080,
            container_name="test-container",
        )

    @pytest.fixture
    def manager(self, config: ContainerConfig) -> ContainerManager:
        """Test container manager."""
        return ContainerManager(config)

    @patch("subprocess.run")
    def test_run_command_success(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test successful command execution."""
        mock_run.return_value = Mock(returncode=0, stdout="success output", stderr="")

        result = manager._run_command(["echo", "test"])

        assert result.success
        assert result.stdout == "success output"
        assert result.stderr == ""
        assert result.return_code == 0
        mock_run.assert_called_once_with(
            ["echo", "test"], capture_output=True, text=True, timeout=300
        )

    @patch("subprocess.run")
    def test_run_command_failure(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test failed command execution."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error message")

        result = manager._run_command(["false"])

        assert not result.success
        assert result.stdout == ""
        assert result.stderr == "error message"
        assert result.return_code == 1

    @patch("subprocess.run")
    def test_run_command_timeout(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test command timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired(["test"], 300)

        result = manager._run_command(["sleep", "1000"])

        assert not result.success
        assert result.stderr == "Command timed out after 5 minutes"
        assert result.return_code == -1

    @patch("subprocess.run")
    def test_run_command_exception(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test unexpected exception handling."""
        mock_run.side_effect = OSError("File not found")

        result = manager._run_command(["nonexistent"])

        assert not result.success
        assert "Unexpected error: File not found" in result.stderr
        assert result.return_code == -1

    @patch("subprocess.run")
    def test_build_success(self, mock_run: Mock, manager: ContainerManager) -> None:
        """Test successful image build."""
        mock_run.return_value = Mock(
            returncode=0, stdout="Successfully built test-image", stderr=""
        )

        result = manager.build()

        assert result.success
        mock_run.assert_called_once_with(
            ["podman", "build", "-t", "test-image", "-f", "test.dockerfile", "."],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_build_with_rebuild(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test image build with no cache."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        manager.build(rebuild=True)

        expected_cmd = [
            "podman",
            "build",
            "-t",
            "test-image",
            "--no-cache",
            "-f",
            "test.dockerfile",
            ".",
        ]
        mock_run.assert_called_once_with(
            expected_cmd, capture_output=True, text=True, timeout=300
        )

    @patch("subprocess.run")
    def test_run_container_detached(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test running container in detached mode."""
        mock_run.return_value = Mock(returncode=0, stdout="container_id_123", stderr="")

        result = manager.run()

        assert result.success
        expected_cmd = [
            "podman",
            "run",
            "-d",
            "-p",
            "8080:80",
            "--name",
            "test-container",
            "test-image",
        ]
        mock_run.assert_called_once_with(
            expected_cmd, capture_output=True, text=True, timeout=300
        )

    @patch("subprocess.run")
    def test_run_container_interactive(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test running container in interactive mode."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        manager.run(detached=False)

        expected_cmd = [
            "podman",
            "run",
            "-p",
            "8080:80",
            "--name",
            "test-container",
            "test-image",
        ]
        mock_run.assert_called_once_with(
            expected_cmd, capture_output=True, text=True, timeout=300
        )

    @patch("subprocess.run")
    def test_run_container_custom_port(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test running container with custom port mapping."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        manager.run(port_mapping="9090:80")

        expected_cmd = [
            "podman",
            "run",
            "-d",
            "-p",
            "9090:80",
            "--name",
            "test-container",
            "test-image",
        ]
        mock_run.assert_called_once_with(
            expected_cmd, capture_output=True, text=True, timeout=300
        )

    @patch("subprocess.run")
    def test_stop_container(self, mock_run: Mock, manager: ContainerManager) -> None:
        """Test stopping container."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = manager.stop()

        assert result.success
        mock_run.assert_called_once_with(
            ["podman", "stop", "test-container"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_remove_container(self, mock_run: Mock, manager: ContainerManager) -> None:
        """Test removing container."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = manager.remove_container()

        assert result.success
        mock_run.assert_called_once_with(
            ["podman", "rm", "test-container"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_remove_container_force(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test force removing container."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        manager.remove_container(force=True)

        mock_run.assert_called_once_with(
            ["podman", "rm", "-f", "test-container"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_remove_image(self, mock_run: Mock, manager: ContainerManager) -> None:
        """Test removing image."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = manager.remove_image()

        assert result.success
        mock_run.assert_called_once_with(
            ["podman", "rmi", "test-image"], capture_output=True, text=True, timeout=300
        )

    @patch("subprocess.run")
    def test_list_containers(self, mock_run: Mock, manager: ContainerManager) -> None:
        """Test listing containers."""
        mock_run.return_value = Mock(
            returncode=0, stdout='[{"name": "test-container"}]', stderr=""
        )

        result = manager.list_containers()

        assert result.success
        mock_run.assert_called_once_with(
            ["podman", "ps", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_list_all_containers(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test listing all containers."""
        mock_run.return_value = Mock(returncode=0, stdout="[]", stderr="")

        manager.list_containers(all_containers=True)

        mock_run.assert_called_once_with(
            ["podman", "ps", "--format", "json", "-a"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_logs(self, mock_run: Mock, manager: ContainerManager) -> None:
        """Test getting container logs."""
        mock_run.return_value = Mock(returncode=0, stdout="log output", stderr="")

        result = manager.logs()

        assert result.success
        mock_run.assert_called_once_with(
            ["podman", "logs", "test-container"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_logs_with_options(self, mock_run: Mock, manager: ContainerManager) -> None:
        """Test getting container logs with options."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        manager.logs(follow=True, tail=100)

        mock_run.assert_called_once_with(
            ["podman", "logs", "-f", "--tail", "100", "test-container"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_inspect(self, mock_run: Mock, manager: ContainerManager) -> None:
        """Test inspecting container."""
        mock_run.return_value = Mock(
            returncode=0, stdout='{"Config": {"Image": "test-image"}}', stderr=""
        )

        result = manager.inspect()

        assert result.success
        mock_run.assert_called_once_with(
            ["podman", "inspect", "test-container"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_execute_command(self, mock_run: Mock, manager: ContainerManager) -> None:
        """Test executing command in container."""
        mock_run.return_value = Mock(returncode=0, stdout="command output", stderr="")

        result = manager.execute_command(["ls", "-la", "/etc"])

        assert result.success
        assert result.stdout == "command output"
        mock_run.assert_called_once_with(
            ["podman", "exec", "test-container", "ls", "-la", "/etc"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_execute_command_failure(
        self, mock_run: Mock, manager: ContainerManager
    ) -> None:
        """Test executing command in container that fails."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="command failed")

        result = manager.execute_command(["invalid-command"])

        assert not result.success
        assert result.stderr == "command failed"
        mock_run.assert_called_once_with(
            ["podman", "exec", "test-container", "invalid-command"],
            capture_output=True,
            text=True,
            timeout=300,
        )


class TestContainerConfigs:
    """Test container configuration functions."""

    def test_get_apache_config(self) -> None:
        """Test getting Apache configuration."""
        config = get_container_config("apache")

        assert config.image_name == "net-servers-apache"
        assert config.dockerfile == "docker/apache/Dockerfile"
        assert config.port == 8080
        assert config.container_name == "net-servers-apache"

    def test_get_mail_config(self) -> None:
        """Test getting mail configuration."""
        config = get_container_config("mail")

        assert config.image_name == "net-servers-mail"
        assert config.dockerfile == "docker/mail/Dockerfile"
        assert config.port == 25
        assert config.container_name == "net-servers-mail"

    def test_get_dns_config(self) -> None:
        """Test getting DNS configuration."""
        config = get_container_config("dns")

        assert config.image_name == "net-servers-dns"
        assert config.dockerfile == "docker/dns/Dockerfile"
        assert config.port == 53
        assert config.container_name == "net-servers-dns"

    def test_get_unknown_config(self) -> None:
        """Test getting unknown configuration raises error."""
        with pytest.raises(ValueError, match="Unknown container config 'unknown'"):
            get_container_config("unknown")
