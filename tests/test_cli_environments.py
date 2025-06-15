"""Tests for environment management CLI commands."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from net_servers.cli_environments import (
    _get_environments_config_path,
    add_environment,
    environments,
    init_environments,
    list_environments,
    show_current,
    show_environment_info,
    switch_environment,
)
from net_servers.config.schemas import EnvironmentConfig


class TestEnvironmentConfigPath:
    """Test environment configuration path detection."""

    @patch("os.environ.get")
    @patch("os.path.exists")
    def test_get_environments_config_path_from_env_var(self, mock_exists, mock_env_get):
        """Test path detection from environment variable."""
        mock_env_get.return_value = "/custom/path/environments.yaml"
        mock_exists.side_effect = lambda path: path == "/custom/path/environments.yaml"

        path = _get_environments_config_path()
        assert path == "/custom/path/environments.yaml"

    @patch("os.environ.get")
    @patch("os.path.exists")
    def test_get_environments_config_path_container_fallback(
        self, mock_exists, mock_env_get
    ):
        """Test fallback to container path when /data exists."""
        mock_env_get.return_value = None  # No env var set
        mock_exists.side_effect = lambda path: path in [
            "/data",
            "/data/environments.yaml",
        ]

        path = _get_environments_config_path()
        assert path == "/data/environments.yaml"

    @patch("os.environ.get")
    @patch("os.path.exists")
    @patch("os.path.abspath")
    def test_get_environments_config_path_project_fallback(
        self, mock_abspath, mock_exists, mock_env_get
    ):
        """Test fallback to project directory."""
        mock_env_get.return_value = None  # No env var set
        mock_exists.return_value = False  # Nothing exists
        mock_abspath.return_value = "/project/environments.yaml"

        path = _get_environments_config_path()
        assert path == "/project/environments.yaml"
        mock_abspath.assert_called_once_with("./environments.yaml")

    @patch("os.environ.get")
    @patch("os.path.exists")
    def test_get_environments_config_path_env_var_not_exists(
        self, mock_exists, mock_env_get
    ):
        """Test env var path that doesn't exist falls back."""
        mock_env_get.return_value = "/nonexistent/path/environments.yaml"
        mock_exists.side_effect = lambda path: path in [
            "/data",
            "/data/environments.yaml",
        ]

        path = _get_environments_config_path()
        # Should fall back to container path since env var path doesn't exist
        assert path == "/data/environments.yaml"

    def test_cli_environments_imports(self):
        """Test that all CLI environment functions are importable."""
        # This test ensures all public functions are accessible
        from net_servers.cli_environments import (
            add_environment,
            environments,
            init_environments,
            list_environments,
            show_current,
            show_environment_info,
            switch_environment,
        )

        # Verify functions are callable
        assert callable(add_environment)
        assert callable(environments)
        assert callable(init_environments)
        assert callable(list_environments)
        assert callable(show_current)
        assert callable(show_environment_info)
        assert callable(switch_environment)


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

    @patch("net_servers.cli_environments._get_environments_config")
    def test_list_environments_success(self, mock_get_environments_config):
        """Test successful environment listing."""
        from net_servers.config.manager import EnvironmentsConfig

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

        mock_config = EnvironmentsConfig(
            current_environment="development", environments=[mock_env1, mock_env2]
        )
        mock_get_environments_config.return_value = ("/fake/path", mock_config)

        result = self.runner.invoke(list_environments)

        assert result.exit_code == 0
        assert "development" in result.output
        assert "staging" in result.output
        assert "Development environment" in result.output

    @patch("net_servers.cli_environments._get_environments_config")
    def test_list_environments_error(self, mock_get_environments_config):
        """Test environment listing error handling."""
        mock_get_environments_config.side_effect = Exception("Config error")

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

    @patch("net_servers.cli_environments._get_environments_config")
    @patch("net_servers.cli_environments._save_environments_config")
    @patch("net_servers.config.schemas.ConfigurationPaths")
    def test_switch_environment_success(
        self, mock_paths, mock_save_config, mock_get_environments_config
    ):
        """Test successful environment switching."""
        # Mock environment
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

        # Mock environments config
        from net_servers.config.schemas import EnvironmentsConfig

        mock_env_config = EnvironmentsConfig(
            current_environment="development", environments=[mock_env]
        )

        mock_get_environments_config.return_value = (
            "/test/config/environments.yaml",
            mock_env_config,
        )

        # Mock configuration paths
        mock_paths_instance = Mock()
        mock_paths.return_value = mock_paths_instance

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

    @patch("net_servers.cli_environments.ConfigurationManager")
    def test_init_environments_success(self, mock_config_manager):
        """Test successful environment initialization."""
        # Mock the configuration manager
        mock_manager_instance = Mock()
        mock_manager_instance.list_environments.return_value = []
        mock_manager_instance.environments_config.current_environment = "development"
        mock_config_manager.return_value = mock_manager_instance

        # Use isolated filesystem for testing
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(init_environments)

            assert result.exit_code == 0
            assert "Created environments configuration" in result.output

            # Check that files were created in current directory
            config_file = Path("./environments.yaml")
            assert config_file.exists()

            # Verify the content structure
            import yaml

            with open(config_file) as f:
                config_data = yaml.safe_load(f)

            assert config_data["current_environment"] == "development"
            assert (
                len(config_data["environments"]) == 4
            )  # dev, staging, testing, production

    def test_init_environments_existing_config(self):
        """Test initialization with existing config."""
        # Use isolated filesystem for testing
        with self.runner.isolated_filesystem():
            # Create existing config
            config_file = Path("./environments.yaml")
            config_file.touch()

            result = self.runner.invoke(init_environments)

            assert result.exit_code == 0
            assert "Environments configuration already exists" in result.output

    @patch("net_servers.cli_environments.ConfigurationManager")
    def test_init_environments_force_flag(self, mock_config_manager):
        """Test initialization with force flag."""
        # Mock the configuration manager
        mock_manager_instance = Mock()
        mock_manager_instance.list_environments.return_value = []
        mock_manager_instance.environments_config.current_environment = "development"
        mock_config_manager.return_value = mock_manager_instance

        # Use isolated filesystem for testing
        with self.runner.isolated_filesystem():
            # Create existing config
            config_file = Path("./environments.yaml")
            config_file.touch()

            result = self.runner.invoke(init_environments, ["--force"])

            assert result.exit_code == 0
            assert "Created environments configuration" in result.output


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
