"""Tests for environment management CLI commands."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from net_servers.cli_environments import (
    add_environment,
    environments,
    init_environments,
    list_environments,
    show_current,
    show_environment_info,
    switch_environment,
)
from net_servers.config.schemas import EnvironmentConfig


class TestEnvironmentsCLI:
    """Test environment CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("net_servers.cli_environments._get_config_manager")
    def test_list_environments_success(self, mock_get_config_manager):
        """Test successful environment listing."""
        mock_manager = Mock()
        mock_env1 = EnvironmentConfig(
            name="development",
            description="Development environment",
            base_path="/test/dev",
            domain="local.dev",
            admin_email="admin@local.dev",
            enabled=True,
            created_at="2024-01-01T00:00:00",
            last_used="2024-01-01T00:00:00",
        )
        mock_env2 = EnvironmentConfig(
            name="staging",
            description="Staging environment",
            base_path="/test/staging",
            domain="staging.local.dev",
            admin_email="admin@local.dev",
            enabled=False,
            created_at="2024-01-01T00:00:00",
            last_used="2024-01-01T00:00:00",
        )
        mock_manager.list_environments.return_value = [mock_env1, mock_env2]
        mock_manager.environments_config.current_environment = "development"
        mock_get_config_manager.return_value = mock_manager

        result = self.runner.invoke(list_environments)

        assert result.exit_code == 0
        assert "development" in result.output
        assert "staging" in result.output
        assert "Development environment" in result.output

    @patch("net_servers.cli_environments._get_config_manager")
    def test_list_environments_error(self, mock_get_config_manager):
        """Test environment listing error handling."""
        mock_get_config_manager.side_effect = Exception("Config error")

        result = self.runner.invoke(list_environments)

        assert result.exit_code == 1
        assert "Error listing environments" in result.output

    @patch("net_servers.cli_environments._get_config_manager")
    def test_show_current_success(self, mock_get_config_manager):
        """Test successful current environment display."""
        mock_manager = Mock()
        mock_env = EnvironmentConfig(
            name="development",
            description="Development environment",
            base_path="/test/dev",
            domain="local.dev",
            admin_email="admin@local.dev",
            enabled=True,
            tags=["development", "local"],
            created_at="2024-01-01T00:00:00",
            last_used="2024-01-01T00:00:00",
        )
        mock_manager.get_current_environment.return_value = mock_env
        mock_get_config_manager.return_value = mock_manager

        result = self.runner.invoke(show_current)

        assert result.exit_code == 0
        assert "Current Environment: development" in result.output
        assert "Domain: local.dev" in result.output

    @patch("net_servers.cli_environments._get_config_manager")
    def test_show_current_error(self, mock_get_config_manager):
        """Test current environment error handling."""
        mock_get_config_manager.side_effect = Exception("Config error")

        result = self.runner.invoke(show_current)

        assert result.exit_code == 1
        assert "Error getting current environment" in result.output

    @patch("net_servers.cli_environments._get_config_manager")
    def test_switch_environment_success(self, mock_get_config_manager):
        """Test successful environment switching."""
        mock_manager = Mock()
        mock_env = EnvironmentConfig(
            name="staging",
            description="Staging environment",
            base_path="/test/staging",
            domain="staging.local.dev",
            admin_email="admin@local.dev",
            enabled=True,
            created_at="2024-01-01T00:00:00",
            last_used="2024-01-01T00:00:00",
        )
        mock_manager.switch_environment.return_value = mock_env
        mock_get_config_manager.return_value = mock_manager

        result = self.runner.invoke(switch_environment, ["staging"])

        assert result.exit_code == 0
        assert "Switched to environment 'staging'" in result.output

    @patch("net_servers.cli_environments._get_config_manager")
    def test_switch_environment_error(self, mock_get_config_manager):
        """Test environment switching error handling."""
        mock_manager = Mock()
        mock_manager.switch_environment.side_effect = ValueError(
            "Environment not found"
        )
        mock_get_config_manager.return_value = mock_manager

        result = self.runner.invoke(switch_environment, ["nonexistent"])

        assert result.exit_code == 1
        assert "Error switching environment" in result.output

    @patch("net_servers.cli_environments._get_config_manager")
    def test_add_environment_success(self, mock_get_config_manager):
        """Test successful environment addition."""
        mock_manager = Mock()
        mock_env = EnvironmentConfig(
            name="testing",
            description="Testing environment",
            base_path="/test/testing",
            domain="test.local.dev",
            admin_email="admin@local.dev",
            enabled=True,
            created_at="2024-01-01T00:00:00",
            last_used="2024-01-01T00:00:00",
        )
        mock_manager.add_environment.return_value = mock_env
        mock_get_config_manager.return_value = mock_manager

        result = self.runner.invoke(
            add_environment,
            [
                "testing",
                "--description",
                "Testing environment",
                "--base-path",
                "/test/testing",
                "--domain",
                "test.local.dev",
                "--admin-email",
                "admin@local.dev",
                "--tag",
                "testing",
                "--tag",
                "ci-cd",
            ],
        )

        assert result.exit_code == 0
        assert "Created environment 'testing'" in result.output

    @patch("net_servers.cli_environments._get_config_manager")
    def test_add_environment_error(self, mock_get_config_manager):
        """Test environment addition error handling."""
        mock_manager = Mock()
        mock_manager.add_environment.side_effect = ValueError("Environment exists")
        mock_get_config_manager.return_value = mock_manager

        result = self.runner.invoke(
            add_environment,
            [
                "existing",
                "--description",
                "Test",
                "--base-path",
                "/test",
                "--domain",
                "test.dev",
                "--admin-email",
                "test@test.dev",
            ],
        )

        assert result.exit_code == 1
        assert "Error adding environment" in result.output

    @patch("net_servers.cli_environments._get_config_manager")
    def test_show_environment_info_success(self, mock_get_config_manager):
        """Test successful environment info display."""
        mock_manager = Mock()
        mock_env = EnvironmentConfig(
            name="production",
            description="Production environment",
            base_path="/test/prod",
            domain="example.com",
            admin_email="admin@example.com",
            enabled=True,
            tags=["production", "live"],
            created_at="2024-01-01T00:00:00",
            last_used="2024-01-01T12:00:00",
        )
        mock_manager.get_environment.return_value = mock_env
        mock_get_config_manager.return_value = mock_manager

        result = self.runner.invoke(show_environment_info, ["production"])

        assert result.exit_code == 0
        assert "Environment: production" in result.output
        assert "Domain: example.com" in result.output

    @patch("net_servers.cli_environments._get_config_manager")
    def test_show_environment_info_not_found(self, mock_get_config_manager):
        """Test environment info for non-existent environment."""
        mock_manager = Mock()
        mock_manager.get_environment.return_value = None
        mock_get_config_manager.return_value = mock_manager

        result = self.runner.invoke(show_environment_info, ["nonexistent"])

        assert result.exit_code == 1
        assert "Environment 'nonexistent' not found" in result.output


class TestInitEnvironments:
    """Test environment initialization."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("net_servers.cli_environments.Path.home")
    @patch("net_servers.cli_environments.ConfigurationManager")
    def test_init_environments_success(self, mock_config_manager, mock_home):
        """Test successful environment initialization."""
        mock_home.return_value = Path(self.temp_dir)

        # Mock the configuration manager
        mock_manager_instance = Mock()
        mock_manager_instance.list_environments.return_value = []
        mock_manager_instance.environments_config.current_environment = "development"
        mock_config_manager.return_value = mock_manager_instance

        result = self.runner.invoke(init_environments)

        assert result.exit_code == 0
        assert "Initialized environments configuration" in result.output

        # Check that directories were created
        config_path = Path(self.temp_dir) / ".net-servers" / "config"
        assert config_path.exists()

    @patch("net_servers.cli_environments.Path.home")
    def test_init_environments_existing_config(self, mock_home):
        """Test initialization with existing config."""
        mock_home.return_value = Path(self.temp_dir)

        # Create existing config
        config_path = Path(self.temp_dir) / ".net-servers" / "config"
        config_path.mkdir(parents=True)
        (config_path / "environments.yaml").touch()

        result = self.runner.invoke(init_environments)

        assert result.exit_code == 0
        assert "Environments configuration already exists" in result.output

    @patch("net_servers.cli_environments.Path.home")
    def test_init_environments_force_flag(self, mock_home):
        """Test initialization with force flag."""
        mock_home.return_value = Path(self.temp_dir)

        # Create existing config
        config_path = Path(self.temp_dir) / ".net-servers" / "config"
        config_path.mkdir(parents=True)
        (config_path / "environments.yaml").touch()

        with patch(
            "net_servers.cli_environments.ConfigurationManager"
        ) as mock_config_manager:
            mock_manager_instance = Mock()
            mock_manager_instance.list_environments.return_value = []
            mock_manager_instance.environments_config.current_environment = (
                "development"
            )
            mock_config_manager.return_value = mock_manager_instance

            result = self.runner.invoke(init_environments, ["--force"])

            assert result.exit_code == 0
            assert "Initialized environments configuration" in result.output


class TestEnvironmentHelpers:
    """Test environment helper functions."""

    def test_environments_help_command(self):
        """Test environments help command."""
        runner = CliRunner()
        result = runner.invoke(environments, ["--help"])

        assert result.exit_code == 0
        assert "Environment management commands" in result.output
        assert "list" in result.output
        assert "current" in result.output
        assert "switch" in result.output
