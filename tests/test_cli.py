"""Tests for CLI functionality."""

import json
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from net_servers.actions.container import ContainerResult
from net_servers.cli import container


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
        result = runner.invoke(container, ["list-configs"])

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

        result = runner.invoke(container, ["build", "-c", "apache"])

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

        result = runner.invoke(container, ["build", "-c", "apache", "--rebuild"])

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

        result = runner.invoke(container, ["build", "-c", "apache"])

        assert result.exit_code == 1
        assert "Error message" in result.output
        assert "Build failed with return code 1" in result.output

    def test_build_invalid_config(self, runner: CliRunner) -> None:
        """Test build with invalid configuration."""
        result = runner.invoke(container, ["build", "-c", "invalid"])

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

        result = runner.invoke(container, ["run", "-c", "apache"])

        assert result.exit_code == 0
        assert "Container net-servers-apache started" in result.output
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

        result = runner.invoke(container, ["run", "-c", "apache", "--interactive"])

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
            container, ["run", "-c", "apache", "--port-mapping", "9090:80"]
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

        result = runner.invoke(container, ["stop", "-c", "apache"])

        assert result.exit_code == 0
        assert "Container net-servers-apache stopped" in result.output
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

        result = runner.invoke(container, ["remove", "-c", "apache"])

        assert result.exit_code == 0
        assert "Container net-servers-apache removed" in result.output
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

        result = runner.invoke(container, ["remove", "-c", "apache", "--force"])

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

        result = runner.invoke(container, ["remove-image", "-c", "apache"])

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

        result = runner.invoke(container, ["list-containers"])

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

        result = runner.invoke(container, ["list-containers", "--all"])

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

        result = runner.invoke(container, ["list-containers"])

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

        result = runner.invoke(container, ["logs", "-c", "apache"])

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
            container, ["logs", "-c", "apache", "--follow", "--tail", "100"]
        )

        assert result.exit_code == 0
        mock_manager.logs.assert_called_once_with(follow=True, tail=100)

    def test_help_command(self, runner: CliRunner) -> None:
        """Test help command displays usage information."""
        result = runner.invoke(container, ["--help"])

        assert result.exit_code == 0
        assert "Container management commands" in result.output
        assert "build" in result.output
        assert "run" in result.output
        assert "stop" in result.output

    def test_verbose_flag(self, runner: CliRunner) -> None:
        """Test verbose flag doesn't cause errors."""
        result = runner.invoke(container, ["--verbose", "list-configs"])

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
            container,
            [
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

        result = runner.invoke(container, ["build-all"])

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
        # First call succeeds, second fails
        mock_manager.build.side_effect = [success_result, failure_result]
        mock_manager_class.return_value = mock_manager

        result = runner.invoke(container, ["build-all"])

        assert result.exit_code == 1
        assert "Failed to build: mail" in result.output

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

        result = runner.invoke(container, ["start-all"])

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

        result = runner.invoke(container, ["stop-all"])

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

        result = runner.invoke(container, ["remove-all", "-f"])

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

        result = runner.invoke(container, ["remove-all-images", "-f"])

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

        result = runner.invoke(container, ["clean-all", "-f"])

        assert result.exit_code == 0
        assert "Cleaning all containers and images..." in result.output
        assert "Stopping all containers..." in result.output
        assert "Removing all containers..." in result.output
        assert "Removing all images..." in result.output
        assert "Clean complete!" in result.output
