"""Tests for container management functionality."""

import subprocess
from unittest.mock import Mock, patch

import pytest

from net_servers.actions.container import (
    ContainerConfig,
    ContainerManager,
    ContainerResult,
    VolumeMount,
)
from net_servers.config.containers import get_container_config


class TestVolumeMount:
    """Test VolumeMount dataclass."""

    def test_volume_mount_defaults(self) -> None:
        """Test VolumeMount with default read-write."""
        volume = VolumeMount(host_path="/host/path", container_path="/container/path")

        assert volume.host_path == "/host/path"
        assert volume.container_path == "/container/path"
        assert not volume.read_only

    def test_volume_mount_read_only(self) -> None:
        """Test VolumeMount with read-only flag."""
        volume = VolumeMount(
            host_path="/host/path", container_path="/container/path", read_only=True
        )

        assert volume.read_only

    def test_to_podman_arg_read_write(self) -> None:
        """Test converting to podman argument format for read-write."""
        volume = VolumeMount(host_path="/host/path", container_path="/container/path")

        assert volume.to_podman_arg() == "/host/path:/container/path"

    def test_to_podman_arg_read_only(self) -> None:
        """Test converting to podman argument format for read-only."""
        volume = VolumeMount(
            host_path="/host/path", container_path="/container/path", read_only=True
        )

        assert volume.to_podman_arg() == "/host/path:/container/path:ro"


class TestContainerConfig:
    """Test ContainerConfig dataclass."""

    def test_container_config_defaults(self) -> None:
        """Test default values and auto-generation of container name."""
        config = ContainerConfig(image_name="test-image")

        assert config.image_name == "test-image"
        assert config.dockerfile == "Dockerfile"
        assert config.port == 8080
        assert config.container_name == "test-image"
        assert config.volumes == []
        assert config.environment == {}
        assert config.config_templates == {}
        assert config.state_paths == []

    def test_container_config_with_registry(self) -> None:
        """Test container name generation from image with registry."""
        config = ContainerConfig(image_name="registry.io/org/test-image:latest")

        assert config.container_name == "test-image-latest"

    def test_container_config_explicit_name(self) -> None:
        """Test explicit container name is preserved."""
        config = ContainerConfig(image_name="test-image", container_name="custom-name")

        assert config.container_name == "custom-name"

    def test_container_config_with_volumes(self) -> None:
        """Test ContainerConfig with volumes."""
        volumes = [VolumeMount("/host", "/container")]
        config = ContainerConfig(image_name="test-image", volumes=volumes)

        assert len(config.volumes) == 1
        assert config.volumes[0].host_path == "/host"

    def test_container_config_with_environment(self) -> None:
        """Test ContainerConfig with environment variables."""
        env = {"VAR1": "value1", "VAR2": "value2"}
        config = ContainerConfig(image_name="test-image", environment=env)

        assert config.environment == env


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
    def test_run_container_with_volumes(self, mock_run: Mock) -> None:
        """Test running container with volume mounts."""
        volumes = [
            VolumeMount("/host/config", "/container/config"),
            VolumeMount("/host/data", "/container/data", read_only=True),
        ]
        config = ContainerConfig(
            image_name="test-image",
            container_name="test-container",
            volumes=volumes,
        )
        manager = ContainerManager(config)
        mock_run.return_value = Mock(returncode=0, stdout="container_id_123", stderr="")

        result = manager.run()

        assert result.success
        expected_cmd = [
            "podman",
            "run",
            "-d",
            "-p",
            "8080:80",
            "-v",
            "/host/config:/container/config",
            "-v",
            "/host/data:/container/data:ro",
            "--name",
            "test-container",
            "test-image",
        ]
        mock_run.assert_called_once_with(
            expected_cmd, capture_output=True, text=True, timeout=300
        )

    @patch("subprocess.run")
    def test_run_container_with_environment(self, mock_run: Mock) -> None:
        """Test running container with environment variables."""
        env = {"VAR1": "value1", "VAR2": "value2"}
        config = ContainerConfig(
            image_name="test-image",
            container_name="test-container",
            environment=env,
        )
        manager = ContainerManager(config)
        mock_run.return_value = Mock(returncode=0, stdout="container_id_123", stderr="")

        result = manager.run()

        assert result.success
        expected_cmd = [
            "podman",
            "run",
            "-d",
            "-p",
            "8080:80",
            "-e",
            "VAR1=value1",
            "-e",
            "VAR2=value2",
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
        config = get_container_config(
            "apache", use_config_manager=False, production_mode=True
        )

        assert config.image_name == "net-servers-apache"
        assert config.dockerfile == "docker/apache/Dockerfile"
        assert config.port == 80
        assert config.container_name == "net-servers-apache"

    def test_get_mail_config(self) -> None:
        """Test getting mail configuration."""
        config = get_container_config(
            "mail", use_config_manager=False, production_mode=True
        )

        assert config.image_name == "net-servers-mail"
        assert config.dockerfile == "docker/mail/Dockerfile"
        assert config.port == 25
        assert config.container_name == "net-servers-mail"

    def test_get_dns_config(self) -> None:
        """Test getting DNS configuration."""
        config = get_container_config(
            "dns", use_config_manager=False, production_mode=True
        )

        assert config.image_name == "net-servers-dns"
        assert config.dockerfile == "docker/dns/Dockerfile"
        assert config.port == 53
        assert config.container_name == "net-servers-dns"

    def test_get_unknown_config(self) -> None:
        """Test getting unknown configuration raises error."""
        with pytest.raises(ValueError, match="Unknown container config 'unknown'"):
            get_container_config("unknown")

    def test_get_config_with_config_manager_error_handling(self) -> None:
        """Test getting config with config manager error handling."""
        from unittest.mock import patch

        # Mock ConfigurationManager to raise an exception
        with patch(
            "net_servers.config.containers.ConfigurationManager"
        ) as mock_manager:
            mock_manager.side_effect = PermissionError("No permission")

            # Should still return basic config when config manager fails
            config = get_container_config("apache", use_config_manager=True)

            assert config.image_name == "net-servers-apache"
            assert config.dockerfile == "docker/apache/Dockerfile"
            # Should not have enhanced volumes/environment
            assert len(config.volumes) == 0
            assert len(config.environment) == 0


class TestPortMapping:
    """Test PortMapping functionality."""

    def test_port_mapping_to_podman_arg_tcp(self) -> None:
        """Test PortMapping to_podman_arg for TCP."""
        from net_servers.actions.container import PortMapping

        mapping = PortMapping(host_port=8080, container_port=80, protocol="tcp")
        result = mapping.to_podman_arg()

        assert result == "8080:80/tcp"

    def test_port_mapping_to_podman_arg_udp(self) -> None:
        """Test PortMapping to_podman_arg for UDP."""
        from net_servers.actions.container import PortMapping

        mapping = PortMapping(host_port=5353, container_port=53, protocol="udp")
        result = mapping.to_podman_arg()

        assert result == "5353:53/udp"

    def test_port_mapping_default_protocol(self) -> None:
        """Test PortMapping default protocol."""
        from net_servers.actions.container import PortMapping

        mapping = PortMapping(host_port=8080, container_port=80)
        result = mapping.to_podman_arg()

        assert result == "8080:80/tcp"


class TestVolumeMountMethods:
    """Test VolumeMount functionality."""

    def test_volume_mount_to_podman_arg_read_write(self) -> None:
        """Test VolumeMount to_podman_arg for read-write."""
        from net_servers.actions.container import VolumeMount

        volume = VolumeMount(
            host_path="/host/path", container_path="/container/path", read_only=False
        )
        result = volume.to_podman_arg()

        assert result == "/host/path:/container/path"

    def test_volume_mount_to_podman_arg_read_only(self) -> None:
        """Test VolumeMount to_podman_arg for read-only."""
        from net_servers.actions.container import VolumeMount

        volume = VolumeMount(
            host_path="/host/path", container_path="/container/path", read_only=True
        )
        result = volume.to_podman_arg()

        assert result == "/host/path:/container/path:ro"

    def test_volume_mount_default_read_only(self) -> None:
        """Test VolumeMount default read_only."""
        from net_servers.actions.container import VolumeMount

        volume = VolumeMount(host_path="/host/path", container_path="/container/path")
        result = volume.to_podman_arg()

        assert result == "/host/path:/container/path"

    def test_volume_mount_with_spaces_in_paths(self) -> None:
        """Test VolumeMount with spaces in paths."""
        from net_servers.actions.container import VolumeMount

        volume = VolumeMount(
            host_path="/host path/with spaces",
            container_path="/container path/with spaces",
        )
        result = volume.to_podman_arg()

        assert result == "/host path/with spaces:/container path/with spaces"


class TestContainerConfigPostInit:
    """Test ContainerConfig __post_init__ functionality."""

    def test_container_config_auto_generate_name(self) -> None:
        """Test auto-generation of container name."""
        from net_servers.actions.container import ContainerConfig

        config = ContainerConfig(image_name="registry/org/my-service:latest")

        assert config.container_name == "my-service-latest"

    def test_container_config_manual_name_not_overridden(self) -> None:
        """Test manual container name is not overridden."""
        from net_servers.actions.container import ContainerConfig

        config = ContainerConfig(
            image_name="registry/org/my-service:latest", container_name="custom-name"
        )

        assert config.container_name == "custom-name"

    def test_container_config_simple_image_name(self) -> None:
        """Test simple image name without registry."""
        from net_servers.actions.container import ContainerConfig

        config = ContainerConfig(image_name="simple-service")

        assert config.container_name == "simple-service"


class TestContainerManagerRunEdgeCases:
    """Test ContainerManager run method edge cases."""

    def test_run_mail_container_multiple_ports(self) -> None:
        """Test running mail container with multiple port mappings."""
        from net_servers.actions.container import ContainerConfig, ContainerManager

        config = ContainerConfig(
            image_name="net-servers-mail", container_name="test-mail"
        )

        manager = ContainerManager(config)

        with patch.object(manager, "_run_command") as mock_run:
            mock_run.return_value = ContainerResult(True, "container_id", "", 0)

            result = manager.run()

            # Verify mail-specific port mappings were added
            assert result.success
            assert mock_run.called
            call_args = mock_run.call_args[0][0]  # Get the command arguments

            # Should include multiple -p flags for mail ports
            port_flags = [i for i, arg in enumerate(call_args) if arg == "-p"]
            assert (
                len(port_flags) >= 6
            )  # SMTP, IMAP, POP3, IMAPS, POP3S, SMTP submission

    def test_run_dns_container_port_mapping(self) -> None:
        """Test running DNS container with port mapping."""
        from net_servers.actions.container import ContainerConfig, ContainerManager

        config = ContainerConfig(
            image_name="net-servers-dns", container_name="test-dns", port=5353
        )

        manager = ContainerManager(config)

        with patch.object(manager, "_run_command") as mock_run:
            mock_run.return_value = ContainerResult(True, "container_id", "", 0)

            result = manager.run()

            # Verify DNS port mapping was added
            assert result.success
            assert mock_run.called
            call_args = mock_run.call_args[0][0]

            # Should include -p flag for DNS port
            assert "-p" in call_args
            port_mapping_index = call_args.index("-p") + 1
            assert call_args[port_mapping_index] == "5353:53"

    def test_run_generic_container_fallback(self) -> None:
        """Test running generic container with fallback port mapping."""
        from net_servers.actions.container import ContainerConfig, ContainerManager

        config = ContainerConfig(
            image_name="generic-service", container_name="test-generic", port=9000
        )

        manager = ContainerManager(config)

        with patch.object(manager, "_run_command") as mock_run:
            mock_run.return_value = ContainerResult(True, "container_id", "", 0)

            result = manager.run()

            # Verify generic fallback port mapping was added
            assert result.success
            assert mock_run.called
            call_args = mock_run.call_args[0][0]

            # Should include -p flag for generic port mapping
            assert "-p" in call_args
            port_mapping_index = call_args.index("-p") + 1
            assert call_args[port_mapping_index] == "9000:80"
