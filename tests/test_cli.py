"""Tests for CLI functionality."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from net_servers.actions.container import ContainerResult
from net_servers.cli import cli


class TestCLI:
    """Test CLI commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI runner for testing."""
        return CliRunner()

    @pytest.fixture
    def success_result(self) -> ContainerResult:
        """Mock successful container result."""
        return ContainerResult(
            success=True, stdout="Success output", stderr="", return_code=0
        )

    @pytest.fixture
    def failure_result(self) -> ContainerResult:
        """Mock failed container result."""
        return ContainerResult(
            success=False, stdout="", stderr="Error message", return_code=1
        )

    def test_list_configs(self, runner: CliRunner) -> None:
        """Test list-configs command."""
        result = runner.invoke(cli, ["container", "list-configs"])

        assert result.exit_code == 0
        assert "apache:" in result.output
        assert "mail:" in result.output
        assert "net-servers-apache" in result.output
        assert "net-servers-mail" in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_build_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test successful build command."""
        mock_manager = Mock()
        mock_manager.build.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "build", "-c", "apache"])

        assert result.exit_code == 0
        assert "Success output" in result.output
        assert "Successfully built net-servers-apache" in result.output
        mock_manager.build.assert_called_once_with(rebuild=False)

    @patch("net_servers.cli.ContainerManager")
    def test_build_with_rebuild(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test build command with rebuild flag."""
        mock_manager = Mock()
        mock_manager.build.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "build", "-c", "apache", "--rebuild"])

        assert result.exit_code == 0
        mock_manager.build.assert_called_once_with(rebuild=True)

    @patch("net_servers.cli.ContainerManager")
    def test_build_failure(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        failure_result: ContainerResult,
    ) -> None:
        """Test failed build command."""
        mock_manager = Mock()
        mock_manager.build.return_value = failure_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "build", "-c", "apache"])

        assert result.exit_code == 1
        assert "Error message" in result.output
        assert "Build failed with return code 1" in result.output

    def test_build_invalid_config(self, runner: CliRunner) -> None:
        """Test build with invalid configuration."""
        result = runner.invoke(cli, ["container", "build", "-c", "invalid"])

        assert result.exit_code == 1
        assert "Unknown container config 'invalid'" in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_run_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test successful run command."""
        mock_manager = Mock()
        mock_manager.run.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "run", "-c", "apache"])

        assert result.exit_code == 0
        assert "Container net-servers-apache-development started" in result.output
        mock_manager.run.assert_called_once_with(detached=True, port_mapping=None)

    @patch("net_servers.cli.ContainerManager")
    def test_run_interactive(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test run command in interactive mode."""
        mock_manager = Mock()
        mock_manager.run.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(
            cli, ["container", "run", "-c", "apache", "--interactive"]
        )

        assert result.exit_code == 0
        mock_manager.run.assert_called_once_with(detached=False, port_mapping=None)

    @patch("net_servers.cli.ContainerManager")
    def test_run_with_port_mapping(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test run command with custom port mapping."""
        mock_manager = Mock()
        mock_manager.run.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(
            cli, ["container", "run", "-c", "apache", "--port-mapping", "9090:80"]
        )

        assert result.exit_code == 0
        mock_manager.run.assert_called_once_with(detached=True, port_mapping="9090:80")

    @patch("net_servers.cli.ContainerManager")
    def test_stop_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test successful stop command."""
        mock_manager = Mock()
        mock_manager.stop.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "stop", "-c", "apache"])

        assert result.exit_code == 0
        assert "Container net-servers-apache-development stopped" in result.output
        mock_manager.stop.assert_called_once()

    @patch("net_servers.cli.ContainerManager")
    def test_remove_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test successful remove command."""
        mock_manager = Mock()
        mock_manager.remove_container.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "remove", "-c", "apache"])

        assert result.exit_code == 0
        assert "Container net-servers-apache-development removed" in result.output
        mock_manager.remove_container.assert_called_once_with(force=False)

    @patch("net_servers.cli.ContainerManager")
    def test_remove_force(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test remove command with force flag."""
        mock_manager = Mock()
        mock_manager.remove_container.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "remove", "-c", "apache", "--force"])

        assert result.exit_code == 0
        mock_manager.remove_container.assert_called_once_with(force=True)

    @patch("net_servers.cli.ContainerManager")
    def test_remove_image_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test successful remove-image command."""
        mock_manager = Mock()
        mock_manager.remove_image.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "remove-image", "-c", "apache"])

        assert result.exit_code == 0
        assert "Image net-servers-apache removed" in result.output
        mock_manager.remove_image.assert_called_once_with(force=False)

    @patch("net_servers.cli.ContainerManager")
    def test_list_containers_success(
        self, mock_manager_class: Mock, runner: CliRunner
    ) -> None:
        """Test successful list-containers command."""
        mock_manager = Mock()
        containers_data = [{"Name": "test-container", "Status": "running"}]
        mock_result = ContainerResult(
            success=True, stdout=json.dumps(containers_data), stderr="", return_code=0
        )
        mock_manager.list_containers.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "list-containers"])

        assert result.exit_code == 0
        assert "test-container" in result.output
        assert "running" in result.output
        mock_manager.list_containers.assert_called_once_with(all_containers=False)

    @patch("net_servers.cli.ContainerManager")
    def test_list_containers_all(
        self, mock_manager_class: Mock, runner: CliRunner
    ) -> None:
        """Test list-containers command with --all flag."""
        mock_manager = Mock()
        mock_result = ContainerResult(
            success=True, stdout="[]", stderr="", return_code=0
        )
        mock_manager.list_containers.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "list-containers", "--all"])

        assert result.exit_code == 0
        mock_manager.list_containers.assert_called_once_with(all_containers=True)

    @patch("net_servers.cli.ContainerManager")
    def test_list_containers_invalid_json(
        self, mock_manager_class: Mock, runner: CliRunner
    ) -> None:
        """Test list-containers with invalid JSON output."""
        mock_manager = Mock()
        mock_result = ContainerResult(
            success=True, stdout="invalid json", stderr="", return_code=0
        )
        mock_manager.list_containers.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "list-containers"])

        assert result.exit_code == 0
        assert "invalid json" in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_logs_success(self, mock_manager_class: Mock, runner: CliRunner) -> None:
        """Test successful logs command."""
        mock_manager = Mock()
        mock_result = ContainerResult(
            success=True, stdout="Container log output", stderr="", return_code=0
        )
        mock_manager.logs.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "logs", "-c", "apache"])

        assert result.exit_code == 0
        assert "Container log output" in result.output
        mock_manager.logs.assert_called_once_with(follow=False, tail=None)

    @patch("net_servers.cli.ContainerManager")
    def test_logs_with_options(
        self, mock_manager_class: Mock, runner: CliRunner
    ) -> None:
        """Test logs command with follow and tail options."""
        mock_manager = Mock()
        mock_result = ContainerResult(
            success=True, stdout="Log output", stderr="", return_code=0
        )
        mock_manager.logs.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(
            cli, ["container", "logs", "-c", "apache", "--follow", "--tail", "100"]
        )

        assert result.exit_code == 0
        mock_manager.logs.assert_called_once_with(follow=True, tail=100)

    def test_help_command(self, runner: CliRunner) -> None:
        """Test help command displays usage information."""
        result = runner.invoke(cli, ["container", "--help"])

        assert result.exit_code == 0
        assert "Container management commands" in result.output
        assert "build" in result.output
        assert "run" in result.output
        assert "stop" in result.output

    def test_verbose_flag(self, runner: CliRunner) -> None:
        """Test verbose flag doesn't cause errors."""
        result = runner.invoke(cli, ["--verbose", "container", "list-configs"])

        assert result.exit_code == 0
        assert "apache:" in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_build_with_overrides(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test build command with image name and dockerfile overrides."""
        mock_manager = Mock()
        mock_manager.build.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(
            cli,
            [
                "container",
                "build",
                "-c",
                "apache",
                "--image-name",
                "custom-image",
                "--dockerfile",
                "custom.dockerfile",
            ],
        )

        assert result.exit_code == 0
        # Verify the config was modified with overrides
        mock_manager_class.assert_called_once()
        config = mock_manager_class.call_args[0][0]
        assert config.image_name == "custom-image"
        assert config.dockerfile == "custom.dockerfile"

    @patch("net_servers.cli.ContainerManager")
    def test_build_all_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test build-all command success."""
        mock_manager = Mock()
        mock_manager.build.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "build-all"])

        assert result.exit_code == 0
        assert "Building apache..." in result.output
        assert "Building mail..." in result.output
        assert "Successfully built" in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_build_all_partial_failure(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
        failure_result: ContainerResult,
    ) -> None:
        """Test build-all command with partial failure."""
        mock_manager = Mock()
        # First call succeeds, second fails, third succeeds
        mock_manager.build.side_effect = [
            success_result,
            failure_result,
            success_result,
        ]
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "build-all"])

        assert result.exit_code == 1
        assert "Failed to build mail" in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_start_all_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test start-all command success."""
        mock_manager = Mock()
        mock_manager.run.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "start-all"])

        assert result.exit_code == 0
        assert "Starting apache..." in result.output
        assert "Starting mail..." in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_stop_all_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test stop-all command success."""
        mock_manager = Mock()
        mock_manager.stop.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "stop-all"])

        assert result.exit_code == 0
        assert "Stopping apache..." in result.output
        assert "Stopping mail..." in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_remove_all_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test remove-all command success."""
        mock_manager = Mock()
        mock_manager.remove_container.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "remove-all", "-f"])

        assert result.exit_code == 0
        assert "Removing container apache..." in result.output
        assert "Removing container mail..." in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_remove_all_images_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test remove-all-images command success."""
        mock_manager = Mock()
        mock_manager.remove_image.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "remove-all-images", "-f"])

        assert result.exit_code == 0
        assert "Removing image apache..." in result.output
        assert "Removing image mail..." in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_clean_all_success(
        self,
        mock_manager_class: Mock,
        runner: CliRunner,
        success_result: ContainerResult,
    ) -> None:
        """Test clean-all command success."""
        mock_manager = Mock()
        mock_manager.stop.return_value = success_result
        mock_manager.remove_container.return_value = success_result
        mock_manager.remove_image.return_value = success_result
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "clean-all", "-f"])

        assert result.exit_code == 0
        assert "Cleaning all containers and images..." in result.output
        assert "Stopping all containers..." in result.output
        assert "Removing all containers..." in result.output
        assert "Removing all images..." in result.output
        assert "Clean complete!" in result.output

    def test_integration_test_missing_pytest(self):
        """Test integration test command when pytest is not available."""
        runner = CliRunner()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = runner.invoke(cli, ["container", "test"])

        assert result.exit_code == 1


class TestDisplayFunctions:
    """Test display service info functions."""

    def test_get_service_name_apache(self):
        """Test service name extraction for Apache."""
        from net_servers.cli import _get_service_name

        assert _get_service_name("net-servers-apache-development") == "apache"
        assert _get_service_name("apache-container") == "apache"

    def test_get_service_name_mail(self):
        """Test service name extraction for Mail."""
        from net_servers.cli import _get_service_name

        assert _get_service_name("net-servers-mail") == "mail"
        assert _get_service_name("mail-container") == "mail"

    def test_get_service_name_dns(self):
        """Test service name extraction for DNS."""
        from net_servers.cli import _get_service_name

        assert _get_service_name("net-servers-dns") == "dns"
        assert _get_service_name("dns-container") == "dns"

    def test_get_service_name_unknown(self):
        """Test service name extraction for unknown service."""
        from net_servers.cli import _get_service_name

        assert _get_service_name("unknown-service") == "unknown"
        assert _get_service_name("some-other-container") == "unknown"

    def test_generate_service_urls_apache(self):
        """Test URL generation for Apache service."""
        from net_servers.actions.container import PortMapping
        from net_servers.cli import _generate_service_urls

        port_mappings = [
            PortMapping(host_port=8080, container_port=80),
            PortMapping(host_port=8443, container_port=443),
        ]

        urls = _generate_service_urls("apache", port_mappings)

        expected = ["HTTP: http://localhost:8080", "HTTPS: https://localhost:8443"]
        assert urls == expected

    def test_generate_service_urls_mail(self):
        """Test URL generation for Mail service."""
        from net_servers.actions.container import PortMapping
        from net_servers.cli import _generate_service_urls

        port_mappings = [
            PortMapping(host_port=2525, container_port=25),
            PortMapping(host_port=1144, container_port=143),
            PortMapping(host_port=1110, container_port=110),
            PortMapping(host_port=9993, container_port=993),
            PortMapping(host_port=9995, container_port=995),
            PortMapping(host_port=5870, container_port=587),
        ]

        urls = _generate_service_urls("mail", port_mappings)

        expected = [
            "SMTP: localhost:2525",
            "IMAP: localhost:1144",
            "POP3: localhost:1110",
            "IMAPS: localhost:9993",
            "POP3S: localhost:9995",
            "SMTP-TLS: localhost:5870",
        ]
        assert urls == expected

    def test_generate_service_urls_dns(self):
        """Test URL generation for DNS service."""
        from net_servers.actions.container import PortMapping
        from net_servers.cli import _generate_service_urls

        port_mappings = [
            PortMapping(host_port=5354, container_port=53, protocol="udp"),
            PortMapping(host_port=5354, container_port=53, protocol="tcp"),
        ]

        urls = _generate_service_urls("dns", port_mappings)

        expected = ["DNS: localhost:5354 (udp)", "DNS: localhost:5354 (tcp)"]
        assert urls == expected

    def test_generate_service_urls_unknown(self):
        """Test URL generation for unknown service."""
        from net_servers.actions.container import PortMapping
        from net_servers.cli import _generate_service_urls

        port_mappings = [PortMapping(host_port=8080, container_port=80)]
        urls = _generate_service_urls("unknown", port_mappings)

        assert urls == []

    @patch("net_servers.cli.click.echo")
    def test_display_service_info_with_port_mappings(self, mock_echo):
        """Test display service info with configured port mappings."""
        from net_servers.cli import _display_service_info
        from net_servers.config.containers import get_container_config

        config = get_container_config(
            "apache", use_config_manager=False, environment_name="testing"
        )
        _display_service_info(config)

        # Verify that port mappings and service URLs are displayed
        mock_echo.assert_any_call("Port Mappings:")
        mock_echo.assert_any_call("  8180 -> 80")
        mock_echo.assert_any_call("  8543 -> 443")
        mock_echo.assert_any_call("Service URLs:")
        mock_echo.assert_any_call("  HTTP: http://localhost:8180")
        mock_echo.assert_any_call("  HTTPS: https://localhost:8543")

    @patch("net_servers.cli.click.echo")
    def test_display_service_info_with_custom_port_mapping(self, mock_echo):
        """Test display service info with custom port mapping."""
        from net_servers.cli import _display_service_info
        from net_servers.config.containers import get_container_config

        config = get_container_config(
            "apache", use_config_manager=False, environment_name="testing"
        )
        _display_service_info(config, "9000:80")

        # Verify custom port mapping display
        mock_echo.assert_any_call("Port Mappings:")
        mock_echo.assert_any_call("  9000 -> 80")
        mock_echo.assert_any_call("Service URLs:")
        mock_echo.assert_any_call("  HTTP: http://localhost:9000")

    @patch("net_servers.cli.click.echo")
    def test_display_service_info_with_https_custom_port(self, mock_echo):
        """Test display service info with HTTPS custom port mapping."""
        from net_servers.cli import _display_service_info
        from net_servers.config.containers import get_container_config

        config = get_container_config(
            "apache", use_config_manager=False, environment_name="testing"
        )
        _display_service_info(config, "9443:443")

        # Verify HTTPS custom port mapping display
        mock_echo.assert_any_call("Port Mappings:")
        mock_echo.assert_any_call("  9443 -> 443")
        mock_echo.assert_any_call("Service URLs:")
        mock_echo.assert_any_call("  HTTP: http://localhost:9443")
        mock_echo.assert_any_call("  HTTPS: https://localhost:9443")

    @patch("net_servers.cli.click.echo")
    def test_display_service_info_fallback_legacy_port(self, mock_echo):
        """Test display service info fallback for legacy port configuration."""
        from net_servers.actions.container import ContainerConfig
        from net_servers.cli import _display_service_info

        # Create a config without port mappings to trigger fallback
        config = ContainerConfig(
            image_name="test-service", port=8080, container_name="test-container"
        )
        _display_service_info(config)

        # Verify fallback display
        mock_echo.assert_any_call("Port Mappings:")
        mock_echo.assert_any_call("  8080 -> (container port)")


class TestCLIErrorHandling:
    """Test CLI error handling scenarios."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI runner for testing."""
        return CliRunner()

    @patch("net_servers.cli.get_container_config")
    def test_build_invalid_config_value_error(
        self, mock_get_config, runner: CliRunner
    ) -> None:
        """Test build command with invalid config raises ValueError."""
        mock_get_config.side_effect = ValueError("Invalid config")

        result = runner.invoke(cli, ["container", "build", "-c", "invalid"])

        assert result.exit_code == 1
        assert "Error: Invalid config" in result.output

    @patch("net_servers.cli.get_container_config")
    def test_run_invalid_config_value_error(
        self, mock_get_config, runner: CliRunner
    ) -> None:
        """Test run command with invalid config raises ValueError."""
        mock_get_config.side_effect = ValueError("Invalid config")

        result = runner.invoke(cli, ["container", "run", "-c", "invalid"])

        assert result.exit_code == 1
        assert "Error: Invalid config" in result.output

    @patch("net_servers.cli.get_container_config")
    def test_stop_invalid_config_value_error(
        self, mock_get_config, runner: CliRunner
    ) -> None:
        """Test stop command with invalid config raises ValueError."""
        mock_get_config.side_effect = ValueError("Invalid config")

        result = runner.invoke(cli, ["container", "stop", "-c", "invalid"])

        assert result.exit_code == 1
        assert "Error: Invalid config" in result.output

    @patch("net_servers.cli.get_container_config")
    def test_remove_invalid_config_value_error(
        self, mock_get_config, runner: CliRunner
    ) -> None:
        """Test remove command with invalid config raises ValueError."""
        mock_get_config.side_effect = ValueError("Invalid config")

        result = runner.invoke(cli, ["container", "remove", "-c", "invalid"])

        assert result.exit_code == 1
        assert "Error: Invalid config" in result.output

    @patch("net_servers.cli.get_container_config")
    def test_remove_image_invalid_config_value_error(
        self, mock_get_config, runner: CliRunner
    ) -> None:
        """Test remove-image command with invalid config raises ValueError."""
        mock_get_config.side_effect = ValueError("Invalid config")

        result = runner.invoke(cli, ["container", "remove-image", "-c", "invalid"])

        assert result.exit_code == 1
        assert "Error: Invalid config" in result.output

    @patch("net_servers.cli.get_container_config")
    def test_logs_invalid_config_value_error(
        self, mock_get_config, runner: CliRunner
    ) -> None:
        """Test logs command with invalid config raises ValueError."""
        mock_get_config.side_effect = ValueError("Invalid config")

        result = runner.invoke(cli, ["container", "logs", "-c", "invalid"])

        assert result.exit_code == 1
        assert "Error: Invalid config" in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_run_command_uses_current_environment(
        self, mock_manager_class, runner: CliRunner
    ) -> None:
        """Test run command uses current environment."""
        mock_manager = Mock()
        mock_manager.run.return_value = ContainerResult(True, "container_id", "", 0)
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "run", "-c", "apache"])

        assert result.exit_code == 0
        assert "Container net-servers-apache-development started" in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_build_command_uses_current_environment(
        self, mock_manager_class, runner: CliRunner
    ) -> None:
        """Test build command uses current environment."""
        mock_manager = Mock()
        mock_manager.build.return_value = ContainerResult(True, "build output", "", 0)
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "build", "-c", "apache"])

        assert result.exit_code == 0
        assert "Successfully built net-servers-apache" in result.output

    @patch("net_servers.cli.ContainerManager")
    def test_stop_command_uses_current_environment(
        self, mock_manager_class, runner: CliRunner
    ) -> None:
        """Test stop command uses current environment."""
        mock_manager = Mock()
        mock_manager.stop.return_value = ContainerResult(True, "", "", 0)
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(cli, ["container", "stop", "-c", "apache"])

        assert result.exit_code == 0
        assert "Container net-servers-apache-development stopped" in result.output


class TestIntegrationTestCommand:
    """Test integration test command functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI runner for testing."""
        return CliRunner()

    def test_integration_test_missing_podman(self, runner: CliRunner) -> None:
        """Test integration test command when podman is not available."""
        with patch("subprocess.run") as mock_run:
            # First call succeeds (pytest check), second and third fail (podman checks)
            mock_run.side_effect = [
                Mock(returncode=0),  # pytest --version succeeds
                subprocess.CalledProcessError(1, "podman"),  # /usr/bin/podman fails
                subprocess.CalledProcessError(1, "podman"),  # podman in PATH fails
            ]

            result = runner.invoke(cli, ["container", "test"])

            assert result.exit_code == 1
            assert "Error: podman is required for integration tests" in result.output

    @patch("subprocess.run")
    def test_integration_test_build_specific_container_success(
        self, mock_run, runner: CliRunner
    ) -> None:
        """Test integration test with build flag for specific container."""
        # Mock subprocess calls
        mock_run.side_effect = [
            Mock(returncode=0),  # pytest --version
            Mock(returncode=0),  # podman --version
            Mock(returncode=0),  # final test run
        ]

        with patch("net_servers.cli.ContainerManager") as mock_manager_class:
            mock_manager = Mock()
            mock_manager.build.return_value = ContainerResult(
                True, "build output", "", 0
            )
            mock_manager_class.return_value = mock_manager

            result = runner.invoke(
                cli, ["container", "test", "-c", "apache", "--build"]
            )

            assert result.exit_code == 0
            assert "Building containers before testing..." in result.output
            assert "Successfully built apache container" in result.output

    @patch("subprocess.run")
    def test_integration_test_build_specific_container_failure(
        self, mock_run, runner: CliRunner
    ) -> None:
        """Test integration test with build flag when build fails."""
        # Mock subprocess calls
        mock_run.side_effect = [
            Mock(returncode=0),  # pytest --version
            Mock(returncode=0),  # podman --version
        ]

        with patch("net_servers.cli.ContainerManager") as mock_manager_class:
            mock_manager = Mock()
            mock_manager.build.return_value = ContainerResult(
                False, "", "build failed", 1
            )
            mock_manager_class.return_value = mock_manager

            result = runner.invoke(
                cli, ["container", "test", "-c", "apache", "--build"]
            )

            assert result.exit_code == 1
            assert "Failed to build apache container" in result.output

    @patch("subprocess.run")
    def test_integration_test_build_all_containers_success(
        self, mock_run, runner: CliRunner
    ) -> None:
        """Test integration test with build-all flag."""
        # Mock subprocess calls
        mock_run.side_effect = [
            Mock(returncode=0),  # pytest --version
            Mock(returncode=0),  # podman --version
            Mock(returncode=0),  # final test run
        ]

        with patch("net_servers.cli.ContainerManager") as mock_manager_class:
            mock_manager = Mock()
            mock_manager.build.return_value = ContainerResult(
                True, "build output", "", 0
            )
            mock_manager_class.return_value = mock_manager

            result = runner.invoke(cli, ["container", "test", "--build"])

            assert result.exit_code == 0
            assert "Building containers before testing..." in result.output
            # Should mention building all available containers
            assert "Successfully built apache container" in result.output
            assert "Successfully built mail container" in result.output

    @patch("subprocess.run")
    def test_integration_test_build_all_containers_failure(
        self, mock_run, runner: CliRunner
    ) -> None:
        """Test integration test with build-all flag when one build fails."""
        # Mock subprocess calls
        mock_run.side_effect = [
            Mock(returncode=0),  # pytest --version
            Mock(returncode=0),  # podman --version
        ]

        with patch("net_servers.cli.ContainerManager") as mock_manager_class:
            mock_manager = Mock()
            # First container succeeds, second fails
            mock_manager.build.side_effect = [
                ContainerResult(True, "build output", "", 0),  # apache succeeds
                ContainerResult(False, "", "build failed", 1),  # mail fails
            ]
            mock_manager_class.return_value = mock_manager

            result = runner.invoke(cli, ["container", "test", "--build"])

            assert result.exit_code == 1
            assert "Failed to build mail container" in result.output

    @patch("subprocess.run")
    def test_integration_test_verbose_flag(self, mock_run, runner: CliRunner) -> None:
        """Test integration test with verbose flag."""
        mock_run.side_effect = [
            Mock(returncode=0),  # pytest --version
            Mock(returncode=0),  # podman --version
            Mock(returncode=0),  # final test run
        ]

        result = runner.invoke(cli, ["container", "test", "--verbose"])

        assert result.exit_code == 0
        assert "Running integration tests..." in result.output
        # Check that verbose flags are added to the command
        final_call = mock_run.call_args_list[-1]
        assert "-v" in final_call[0][0]
        assert "-s" in final_call[0][0]

    @patch("subprocess.run")
    def test_integration_test_specific_container(
        self, mock_run, runner: CliRunner
    ) -> None:
        """Test integration test for specific container."""
        mock_run.side_effect = [
            Mock(returncode=0),  # pytest --version
            Mock(returncode=0),  # podman --version
            Mock(returncode=0),  # final test run
        ]

        result = runner.invoke(cli, ["container", "test", "-c", "apache"])

        assert result.exit_code == 0
        # Check that specific test file is targeted
        final_call = mock_run.call_args_list[-1]
        assert "tests/integration/test_apache.py" in final_call[0][0]

    @patch("subprocess.run")
    def test_integration_test_all_containers(self, mock_run, runner: CliRunner) -> None:
        """Test integration test for all containers."""
        mock_run.side_effect = [
            Mock(returncode=0),  # pytest --version
            Mock(returncode=0),  # podman --version
            Mock(returncode=0),  # final test run
        ]

        result = runner.invoke(cli, ["container", "test"])

        assert result.exit_code == 0
        # Check that integration directory is targeted
        final_call = mock_run.call_args_list[-1]
        assert "tests/integration/" in final_call[0][0]

    @patch("subprocess.run")
    def test_integration_test_production_mode(
        self, mock_run, runner: CliRunner
    ) -> None:
        """Test integration test with production mode."""
        mock_run.side_effect = [
            Mock(returncode=0),  # pytest --version
            Mock(returncode=0),  # podman --version
            Mock(returncode=0),  # final test run
        ]

        result = runner.invoke(cli, ["container", "test"])

        assert result.exit_code == 0
        assert "Running integration tests..." in result.output
