"""Unit tests for CLI configuration commands."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from net_servers.cli_config import config
from net_servers.config.manager import ConfigurationManager
from net_servers.config.schemas import DomainConfig, UserConfig


class TestConfigCLI:
    """Test configuration CLI commands."""

    def test_config_help(self):
        """Test config command help."""
        runner = CliRunner()
        result = runner.invoke(config, ["--help"])

        assert result.exit_code == 0
        assert "Configuration management commands" in result.output
        assert "user" in result.output
        assert "domain" in result.output
        assert "init" in result.output

    def test_config_init(self):
        """Test config init command."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(config, ["init", "--base-path", temp_dir])

            assert result.exit_code == 0
            assert "Default configuration initialized" in result.output
            assert "Created configuration files:" in result.output

            # Check files were created
            config_path = Path(temp_dir) / "config"
            assert (config_path / "global.yaml").exists()
            assert (config_path / "users.yaml").exists()
            assert (config_path / "domains.yaml").exists()

    def test_config_init_error_handling(self):
        """Test config init command error handling."""
        runner = CliRunner()

        with patch("net_servers.cli_config.ConfigurationManager") as mock_manager:
            mock_manager.return_value.initialize_default_configs.side_effect = (
                Exception("Test error")
            )

            result = runner.invoke(config, ["init", "--base-path", "/tmp/test"])

            assert (
                result.exit_code == 0
            )  # Click doesn't exit with error code for our exceptions
            assert "Error initializing configuration" in result.output

    def test_config_validate_success(self):
        """Test config validate command with mocked valid configuration."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.validate_all_services.return_value = {
                "mail": [],
                "dns": [],
                "apache": [],
            }
            mock_setup.return_value = mock_sync_manager

            result = runner.invoke(config, ["validate", "--base-path", "/tmp/test"])

            assert result.exit_code == 0
            assert "All service configurations are valid" in result.output

    def test_config_validate_with_errors(self):
        """Test config validate command with validation errors."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.validate_all_services.return_value = {
                "mail": ["Mail error 1", "Mail error 2"],
                "dns": [],
                "apache": ["Apache error"],
            }
            mock_setup.return_value = mock_sync_manager

            result = runner.invoke(config, ["validate", "--base-path", "/tmp/test"])

            assert result.exit_code == 0
            assert "mail validation failed" in result.output
            assert "Mail error 1" in result.output
            assert "apache validation failed" in result.output
            assert "dns configuration is valid" in result.output

    def test_config_validate_error_handling(self):
        """Test config validate command error handling."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_setup.side_effect = Exception("Test validation error")

            result = runner.invoke(config, ["validate", "--base-path", "/tmp/test"])

            assert result.exit_code == 0
            assert "Error validating configuration" in result.output

    def test_config_sync_success(self):
        """Test config sync command."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.sync_all_users.return_value = True
            mock_sync_manager.sync_all_domains.return_value = True
            mock_sync_manager.reload_all_services.return_value = True
            mock_setup.return_value = mock_sync_manager

            result = runner.invoke(config, ["sync", "--base-path", "/tmp/test"])

            assert result.exit_code == 0
            assert "Users synchronized" in result.output
            assert "Domains synchronized" in result.output
            assert "Services reloaded" in result.output

    def test_config_sync_partial_failure(self):
        """Test config sync command with partial failures."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.sync_all_users.return_value = False
            mock_sync_manager.sync_all_domains.return_value = True
            mock_sync_manager.reload_all_services.return_value = False
            mock_setup.return_value = mock_sync_manager

            result = runner.invoke(config, ["sync", "--base-path", "/tmp/test"])

            assert result.exit_code == 0
            assert "Failed to sync users" in result.output
            assert "Domains synchronized" in result.output
            assert "Some services failed to reload" in result.output

    def test_config_sync_error_handling(self):
        """Test config sync command error handling."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_setup.side_effect = Exception("Test sync error")

            result = runner.invoke(config, ["sync", "--base-path", "/tmp/test"])

            assert result.exit_code == 0
            assert "Error synchronizing configuration" in result.output


class TestUserCLI:
    """Test user management CLI commands."""

    def test_user_help(self):
        """Test user command help."""
        runner = CliRunner()
        result = runner.invoke(config, ["user", "--help"])

        assert result.exit_code == 0
        assert "User management commands" in result.output
        assert "add" in result.output
        assert "delete" in result.output
        assert "list" in result.output

    def test_user_add_success(self):
        """Test user add command success."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.add_user.return_value = True
            mock_sync_manager.validate_all_services.return_value = {
                "mail": [],
                "dns": [],
            }
            mock_setup.return_value = mock_sync_manager

            result = runner.invoke(
                config,
                [
                    "user",
                    "add",
                    "-u",
                    "testuser",
                    "-e",
                    "testuser@example.com",
                    "-d",
                    "example.com",
                    "--base-path",
                    "/tmp/test",
                ],
            )

            assert result.exit_code == 0
            assert "Successfully added user: testuser" in result.output
            assert "mail configuration validated" in result.output

    def test_user_add_failure(self):
        """Test user add command failure."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.add_user.return_value = False
            mock_setup.return_value = mock_sync_manager

            result = runner.invoke(
                config,
                [
                    "user",
                    "add",
                    "-u",
                    "testuser",
                    "-e",
                    "testuser@example.com",
                    "--base-path",
                    "/tmp/test",
                ],
            )

            assert result.exit_code == 0
            assert "Failed to add user: testuser" in result.output

    def test_user_add_with_validation_warnings(self):
        """Test user add command with validation warnings."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.add_user.return_value = True
            mock_sync_manager.validate_all_services.return_value = {
                "mail": ["Warning 1", "Warning 2"],
                "dns": [],
            }
            mock_setup.return_value = mock_sync_manager

            result = runner.invoke(
                config,
                [
                    "user",
                    "add",
                    "-u",
                    "testuser",
                    "-e",
                    "testuser@example.com",
                    "-d",
                    "example.com",
                    "-r",
                    "admin",
                    "-q",
                    "1G",
                    "--base-path",
                    "/tmp/test",
                ],
            )

            assert result.exit_code == 0
            assert "Successfully added user: testuser" in result.output
            assert "Validation warnings for mail: Warning 1, Warning 2" in result.output

    def test_user_add_error_handling(self):
        """Test user add command error handling."""
        runner = CliRunner()

        with patch("net_servers.cli_config.UserConfig") as mock_user_config:
            mock_user_config.side_effect = Exception("Invalid user data")

            result = runner.invoke(
                config,
                [
                    "user",
                    "add",
                    "-u",
                    "testuser",
                    "-e",
                    "invalid-email",
                    "--base-path",
                    "/tmp/test",
                ],
            )

            assert result.exit_code == 0
            assert "Error adding user: Invalid user data" in result.output

    def test_user_delete_success_with_confirmation(self):
        """Test user delete command with confirmation."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.delete_user.return_value = True
            mock_setup.return_value = mock_sync_manager

            result = runner.invoke(
                config,
                [
                    "user",
                    "delete",
                    "-u",
                    "testuser",
                    "--confirm",
                    "--base-path",
                    "/tmp/test",
                ],
                input="y\n",
            )

            assert result.exit_code == 0
            assert "Successfully deleted user: testuser" in result.output

    def test_user_delete_cancelled(self):
        """Test user delete command cancelled by user."""
        runner = CliRunner()

        result = runner.invoke(
            config,
            ["user", "delete", "-u", "testuser", "--base-path", "/tmp/test"],
            input="n\n",
        )

        assert result.exit_code == 0
        assert "Operation cancelled" in result.output

    def test_user_delete_failure(self):
        """Test user delete command failure."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.delete_user.return_value = False
            mock_setup.return_value = mock_sync_manager

            result = runner.invoke(
                config,
                [
                    "user",
                    "delete",
                    "-u",
                    "testuser",
                    "--confirm",
                    "--base-path",
                    "/tmp/test",
                ],
            )

            assert result.exit_code == 0
            assert "Failed to delete user: testuser" in result.output

    def test_user_delete_error_handling(self):
        """Test user delete command error handling."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_setup.side_effect = Exception("Delete error")

            result = runner.invoke(
                config,
                [
                    "user",
                    "delete",
                    "-u",
                    "testuser",
                    "--confirm",
                    "--base-path",
                    "/tmp/test",
                ],
            )

            assert result.exit_code == 0
            assert "Error deleting user: Delete error" in result.output

    def test_user_list_success(self):
        """Test user list command."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up test configuration
            config_manager = ConfigurationManager(base_path=temp_dir)
            users_config = config_manager.users_config
            users_config.users = [
                UserConfig(
                    username="user1",
                    email="user1@example.com",
                    domains=["example.com"],
                    roles=["user"],
                    enabled=True,
                ),
                UserConfig(
                    username="user2",
                    email="user2@example.com",
                    domains=["example.com", "test.com"],
                    roles=["admin"],
                    enabled=False,
                ),
            ]
            config_manager.save_users_config(users_config)

            result = runner.invoke(config, ["user", "list", "--base-path", temp_dir])

            assert result.exit_code == 0
            assert "Found 2 users:" in result.output
            assert "Username: user1" in result.output
            assert "user1@example.com" in result.output
            assert "Enabled" in result.output
            assert "Username: user2" in result.output
            assert "Disabled" in result.output

    def test_user_list_empty(self):
        """Test user list command with no users."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            config_manager.save_users_config(config_manager.users_config)

            result = runner.invoke(config, ["user", "list", "--base-path", temp_dir])

            assert result.exit_code == 0
            assert "No users found" in result.output

    def test_user_list_error_handling(self):
        """Test user list command error handling."""
        runner = CliRunner()

        with patch("net_servers.cli_config.ConfigurationManager") as mock_manager:
            mock_manager.side_effect = Exception("List error")

            result = runner.invoke(config, ["user", "list", "--base-path", "/tmp/test"])

            assert result.exit_code == 0
            assert "Error listing users: List error" in result.output


class TestDomainCLI:
    """Test domain management CLI commands."""

    def test_domain_help(self):
        """Test domain command help."""
        runner = CliRunner()
        result = runner.invoke(config, ["domain", "--help"])

        assert result.exit_code == 0
        assert "Domain management commands" in result.output
        assert "add" in result.output
        assert "list" in result.output

    def test_domain_add_success(self):
        """Test domain add command success."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.sync_all_domains.return_value = True
            mock_setup.return_value = mock_sync_manager

            with patch("net_servers.cli_config.ConfigurationManager") as mock_manager:
                mock_config_manager = MagicMock()
                mock_domains_config = MagicMock()
                mock_domains_config.domains = []
                mock_config_manager.domains_config = mock_domains_config
                mock_manager.return_value = mock_config_manager

                result = runner.invoke(
                    config,
                    [
                        "domain",
                        "add",
                        "-n",
                        "example.com",
                        "-m",
                        "mail.example.com",
                        "-a",
                        "www:192.168.1.1",
                        "-a",
                        "mail:192.168.1.2",
                        "--base-path",
                        "/tmp/test",
                    ],
                )

                assert result.exit_code == 0
                assert "Successfully added domain: example.com" in result.output

    def test_domain_add_sync_failure(self):
        """Test domain add command with sync failure."""
        runner = CliRunner()

        with patch("net_servers.cli_config.setup_sync_manager") as mock_setup:
            mock_sync_manager = MagicMock()
            mock_sync_manager.sync_all_domains.return_value = False
            mock_setup.return_value = mock_sync_manager

            with patch("net_servers.cli_config.ConfigurationManager") as mock_manager:
                mock_config_manager = MagicMock()
                mock_manager.return_value = mock_config_manager

                result = runner.invoke(
                    config,
                    ["domain", "add", "-n", "example.com", "--base-path", "/tmp/test"],
                )

                assert result.exit_code == 0
                assert "Failed to sync domain to services: example.com" in result.output

    def test_domain_add_invalid_a_record(self):
        """Test domain add command with invalid A record format."""
        runner = CliRunner()

        result = runner.invoke(
            config,
            [
                "domain",
                "add",
                "-n",
                "example.com",
                "-a",
                "invalid-format",  # Missing colon
                "--base-path",
                "/tmp/test",
            ],
        )

        assert result.exit_code == 0
        assert "Invalid A record format: invalid-format (use name:ip)" in result.output

    def test_domain_add_error_handling(self):
        """Test domain add command error handling."""
        runner = CliRunner()

        with patch("net_servers.cli_config.DomainConfig") as mock_domain_config:
            mock_domain_config.side_effect = Exception("Invalid domain data")

            result = runner.invoke(
                config,
                ["domain", "add", "-n", "example.com", "--base-path", "/tmp/test"],
            )

            assert result.exit_code == 0
            assert "Error adding domain: Invalid domain data" in result.output

    def test_domain_list_success(self):
        """Test domain list command."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up test configuration
            config_manager = ConfigurationManager(base_path=temp_dir)
            domains_config = config_manager.domains_config
            domains_config.domains = [
                DomainConfig(
                    name="example.com",
                    enabled=True,
                    mx_records=["mail.example.com"],
                    a_records={"www": "192.168.1.1", "mail": "192.168.1.2"},
                ),
                DomainConfig(name="disabled.com", enabled=False),
            ]
            config_manager.save_domains_config(domains_config)

            result = runner.invoke(config, ["domain", "list", "--base-path", temp_dir])

            assert result.exit_code == 0
            assert "Found 2 domains:" in result.output
            assert "Domain: example.com" in result.output
            assert "Enabled" in result.output
            assert "MX Records: mail.example.com" in result.output
            assert "A Records: www:192.168.1.1, mail:192.168.1.2" in result.output
            assert "Domain: disabled.com" in result.output
            assert "Disabled" in result.output

    def test_domain_list_empty(self):
        """Test domain list command with no domains."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            config_manager.save_domains_config(config_manager.domains_config)

            result = runner.invoke(config, ["domain", "list", "--base-path", temp_dir])

            assert result.exit_code == 0
            assert "No domains found" in result.output

    def test_domain_list_error_handling(self):
        """Test domain list command error handling."""
        runner = CliRunner()

        with patch("net_servers.cli_config.ConfigurationManager") as mock_manager:
            mock_manager.side_effect = Exception("List error")

            result = runner.invoke(
                config, ["domain", "list", "--base-path", "/tmp/test"]
            )

            assert result.exit_code == 0
            assert "Error listing domains: List error" in result.output


class TestUtilityCLI:
    """Test utility CLI commands."""

    def test_test_email_success(self):
        """Test test-email command success."""
        runner = CliRunner()

        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp_instance = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_smtp_instance

            result = runner.invoke(
                config,
                [
                    "test-email",
                    "-t",
                    "test@example.com",
                    "-s",
                    "Test Subject",
                    "-b",
                    "Test Body",
                    "--base-path",
                    "/tmp/test",
                ],
            )

            assert result.exit_code == 0
            assert "Test email sent to test@example.com" in result.output
            assert "Check the recipient's mailbox" in result.output

    def test_test_email_failure(self):
        """Test test-email command failure."""
        runner = CliRunner()

        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP error")

            result = runner.invoke(
                config,
                ["test-email", "-t", "test@example.com", "--base-path", "/tmp/test"],
            )

            assert result.exit_code == 0
            assert "Failed to send test email: SMTP error" in result.output

    def test_daemon_startup(self):
        """Test daemon command startup."""
        runner = CliRunner()

        with patch("net_servers.config.watcher.ConfigurationDaemon") as mock_daemon:
            mock_daemon_instance = MagicMock()
            mock_daemon.return_value = mock_daemon_instance
            mock_daemon_instance.run.side_effect = KeyboardInterrupt()

            result = runner.invoke(
                config, ["daemon", "--base-path", "/tmp/test", "--debounce", "1.0"]
            )

            assert result.exit_code == 0
            assert "Starting configuration daemon" in result.output
            assert "Daemon stopped by user" in result.output

    def test_daemon_error(self):
        """Test daemon command error handling."""
        runner = CliRunner()

        with patch("net_servers.config.watcher.ConfigurationDaemon") as mock_daemon:
            mock_daemon.side_effect = Exception("Daemon error")

            result = runner.invoke(config, ["daemon", "--base-path", "/tmp/test"])

            assert result.exit_code == 0
            assert "Daemon error: Daemon error" in result.output


class TestSetupSyncManager:
    """Test setup_sync_manager function."""

    def test_setup_sync_manager_success(self):
        """Test successful sync manager setup."""
        from net_servers.cli_config import setup_sync_manager

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "net_servers.cli_config.get_container_config"
            ) as mock_get_config:
                with patch(
                    "net_servers.cli_config.ContainerManager"
                ) as mock_container_manager:
                    mock_get_config.return_value = MagicMock()
                    mock_container_manager.return_value = MagicMock()

                    sync_manager = setup_sync_manager(temp_dir)

                    assert sync_manager is not None
                    # Should have tried to register mail and dns synchronizers
                    assert mock_get_config.call_count >= 2

    def test_setup_sync_manager_with_errors(self):
        """Test sync manager setup with container config errors."""
        from net_servers.cli_config import setup_sync_manager

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "net_servers.cli_config.get_container_config"
            ) as mock_get_config:
                mock_get_config.side_effect = Exception("Container config error")

                # Should not raise exception, just log warning
                sync_manager = setup_sync_manager(temp_dir)
                assert sync_manager is not None
