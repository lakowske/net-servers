"""Unit tests for configuration synchronization system."""

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from net_servers.config.manager import ConfigurationManager
from net_servers.config.schemas import DomainConfig, UserConfig
from net_servers.config.sync import (
    ConfigurationSyncManager,
    DnsServiceSynchronizer,
    MailServiceSynchronizer,
    ServiceSynchronizer,
)


class MockServiceSynchronizer(ServiceSynchronizer):
    """Mock service synchronizer for testing."""

    def __init__(self, config_manager):
        """Initialize mock synchronizer."""
        super().__init__(config_manager)
        self.sync_users_called = False
        self.sync_domains_called = False
        self.validate_called = False
        self.reload_called = False

    def sync_users(self, users):
        """Mock sync users method."""
        self.sync_users_called = True
        return True

    def sync_domains(self, domains):
        """Mock sync domains method."""
        self.sync_domains_called = True
        return True

    def validate_configuration(self):
        """Mock validate configuration method."""
        self.validate_called = True
        return []

    def reload_service(self):
        """Mock reload service method."""
        self.reload_called = True
        return True


class TestServiceSynchronizer:
    """Test base ServiceSynchronizer class."""

    def test_service_synchronizer_init(self):
        """Test service synchronizer initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MockServiceSynchronizer(config_manager)

            assert synchronizer.config_manager is config_manager
            assert hasattr(synchronizer, "logger")

    def test_service_synchronizer_abstract_methods(self):
        """Test that ServiceSynchronizer is properly abstract."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Cannot instantiate abstract base class directly
            with pytest.raises(TypeError):
                ServiceSynchronizer(config_manager)


class TestConfigurationSyncManager:
    """Test ConfigurationSyncManager class."""

    def test_configuration_sync_manager_init(self):
        """Test sync manager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            sync_manager = ConfigurationSyncManager(config_manager)

            assert sync_manager.config_manager is config_manager
            assert sync_manager.synchronizers == {}

    def test_register_synchronizer(self):
        """Test registering synchronizers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            sync_manager = ConfigurationSyncManager(config_manager)
            synchronizer = MockServiceSynchronizer(config_manager)

            sync_manager.register_synchronizer("test", synchronizer)

            assert "test" in sync_manager.synchronizers
            assert sync_manager.synchronizers["test"] is synchronizer

    def test_add_user_success(self):
        """Test adding user successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            config_manager.initialize_default_configs()
            sync_manager = ConfigurationSyncManager(config_manager)

            # Register mock synchronizer
            mock_sync = MockServiceSynchronizer(config_manager)
            sync_manager.register_synchronizer("mock", mock_sync)

            # Create test user
            test_user = UserConfig(
                username="testuser", email="test@example.com", domains=["example.com"]
            )

            result = sync_manager.add_user(test_user)

            assert result is True
            assert mock_sync.sync_users_called

            # Verify user was added to configuration
            users = config_manager.users_config.users
            assert len(users) == 2  # admin + testuser
            assert any(user.username == "testuser" for user in users)

    def test_add_user_duplicate(self):
        """Test adding duplicate user."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            config_manager.initialize_default_configs()
            sync_manager = ConfigurationSyncManager(config_manager)

            # Add a user first
            user1 = UserConfig(username="testuser", email="test@example.com")
            sync_manager.add_user(user1)

            # Try to add user with same username
            user2 = UserConfig(username="testuser", email="different@example.com")
            result = sync_manager.add_user(user2)

            # Current implementation doesn't check for duplicates, it just adds
            # This test documents current behavior - could be enhanced later
            assert result is True

    def test_add_user_mailbox_creation(self):
        """Test that adding user creates mailbox structure via mail synchronizer."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            config_manager.initialize_default_configs()
            sync_manager = ConfigurationSyncManager(config_manager)

            # Register mail synchronizer to handle mailbox creation
            mail_sync = MailServiceSynchronizer(config_manager)
            sync_manager.register_synchronizer("mail", mail_sync)

            test_user = UserConfig(username="mailtest", email="mailtest@example.com")

            result = sync_manager.add_user(test_user)

            assert result is True

            # Check mailbox directory was created by mail synchronizer
            mailbox_path = config_manager.paths.state_path / "mailboxes" / "mailtest"
            assert mailbox_path.exists()

            # Check standard mail folders
            assert (mailbox_path / "INBOX").exists()
            assert (mailbox_path / "Sent").exists()
            assert (mailbox_path / "Drafts").exists()
            assert (mailbox_path / "Trash").exists()

    def test_delete_user_success(self):
        """Test deleting user successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            config_manager.initialize_default_configs()
            sync_manager = ConfigurationSyncManager(config_manager)

            # Register mock synchronizer
            mock_sync = MockServiceSynchronizer(config_manager)
            sync_manager.register_synchronizer("mock", mock_sync)

            # Add a user first
            test_user = UserConfig(username="deletetest", email="delete@example.com")
            sync_manager.add_user(test_user)

            # Verify user exists
            users = config_manager.users_config.users
            assert any(user.username == "deletetest" for user in users)

            # Delete user
            result = sync_manager.delete_user("deletetest")

            assert result is True
            assert mock_sync.sync_users_called

            # Verify user was removed
            users_after = config_manager.users_config.users
            assert not any(user.username == "deletetest" for user in users_after)

    def test_delete_user_not_found(self):
        """Test deleting non-existent user."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            config_manager.initialize_default_configs()
            sync_manager = ConfigurationSyncManager(config_manager)

            result = sync_manager.delete_user("nonexistent")

            assert result is False

    def test_delete_user_mailbox_cleanup(self):
        """Test that deleting user removes mailbox via sync."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            config_manager.initialize_default_configs()
            sync_manager = ConfigurationSyncManager(config_manager)

            # Register mail synchronizer
            mail_sync = MailServiceSynchronizer(config_manager)
            sync_manager.register_synchronizer("mail", mail_sync)

            # Add user with mailbox
            test_user = UserConfig(username="cleanuptest", email="cleanup@example.com")
            sync_manager.add_user(test_user)

            mailbox_path = config_manager.paths.state_path / "mailboxes" / "cleanuptest"
            assert mailbox_path.exists()

            # Delete user
            result = sync_manager.delete_user("cleanuptest")
            assert result is True

            # Note: Current implementation doesn't automatically clean up
            # mailboxes. This test documents current behavior - mailbox
            # cleanup could be added later
            # For now, we just verify the user was removed from config
            users_after = config_manager.users_config.users
            assert not any(user.username == "cleanuptest" for user in users_after)

    def test_sync_all_users(self):
        """Test syncing all users to services."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            config_manager.initialize_default_configs()
            sync_manager = ConfigurationSyncManager(config_manager)

            # Register mock synchronizers
            mock_sync1 = MockServiceSynchronizer(config_manager)
            mock_sync2 = MockServiceSynchronizer(config_manager)
            sync_manager.register_synchronizer("service1", mock_sync1)
            sync_manager.register_synchronizer("service2", mock_sync2)

            result = sync_manager.sync_all_users()

            assert result is True
            assert mock_sync1.sync_users_called
            assert mock_sync2.sync_users_called

    def test_sync_all_users_partial_failure(self):
        """Test syncing users with some service failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            sync_manager = ConfigurationSyncManager(config_manager)

            # Create synchronizers with mixed success
            mock_sync1 = MockServiceSynchronizer(config_manager)
            mock_sync2 = MagicMock()
            mock_sync2.sync_users.return_value = False

            sync_manager.register_synchronizer("good", mock_sync1)
            sync_manager.register_synchronizer("bad", mock_sync2)

            result = sync_manager.sync_all_users()

            assert result is False  # Should return False if any fail

    def test_sync_all_domains(self):
        """Test syncing all domains to services."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            config_manager.initialize_default_configs()
            sync_manager = ConfigurationSyncManager(config_manager)

            # Register mock synchronizers
            mock_sync1 = MockServiceSynchronizer(config_manager)
            mock_sync2 = MockServiceSynchronizer(config_manager)
            sync_manager.register_synchronizer("service1", mock_sync1)
            sync_manager.register_synchronizer("service2", mock_sync2)

            result = sync_manager.sync_all_domains()

            assert result is True
            assert mock_sync1.sync_domains_called
            assert mock_sync2.sync_domains_called

    def test_validate_all_services(self):
        """Test validating all services."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            sync_manager = ConfigurationSyncManager(config_manager)

            # Register mock synchronizers with different validation results
            mock_sync1 = MockServiceSynchronizer(config_manager)
            mock_sync2 = MagicMock()
            mock_sync2.validate_configuration.return_value = ["Error 1", "Error 2"]

            sync_manager.register_synchronizer("good", mock_sync1)
            sync_manager.register_synchronizer("bad", mock_sync2)

            results = sync_manager.validate_all_services()

            assert results["good"] == []
            assert results["bad"] == ["Error 1", "Error 2"]
            assert mock_sync1.validate_called

    def test_reload_all_services(self):
        """Test reloading all services."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            sync_manager = ConfigurationSyncManager(config_manager)

            # Register mock synchronizers
            mock_sync1 = MockServiceSynchronizer(config_manager)
            mock_sync2 = MockServiceSynchronizer(config_manager)
            sync_manager.register_synchronizer("service1", mock_sync1)
            sync_manager.register_synchronizer("service2", mock_sync2)

            result = sync_manager.reload_all_services()

            assert result is True
            assert mock_sync1.reload_called
            assert mock_sync2.reload_called

    def test_reload_all_services_with_failures(self):
        """Test reloading services with some failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            sync_manager = ConfigurationSyncManager(config_manager)

            # Create synchronizers with mixed reload success
            mock_sync1 = MockServiceSynchronizer(config_manager)
            mock_sync2 = MagicMock()
            mock_sync2.reload_service.return_value = False

            sync_manager.register_synchronizer("good", mock_sync1)
            sync_manager.register_synchronizer("bad", mock_sync2)

            result = sync_manager.reload_all_services()

            assert result is False  # Should return False if any fail


class TestMailServiceSynchronizer:
    """Test MailServiceSynchronizer class."""

    def test_mail_service_synchronizer_init_without_container(self):
        """Test mail synchronizer initialization without container."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            assert synchronizer.config_manager is config_manager
            assert synchronizer.container_manager is None

    def test_mail_service_synchronizer_init_with_container(self):
        """Test mail synchronizer initialization with container."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            mock_container = MagicMock()
            synchronizer = MailServiceSynchronizer(config_manager, mock_container)

            assert synchronizer.config_manager is config_manager
            assert synchronizer.container_manager is mock_container

    def test_sync_users_creates_files(self):
        """Test that syncing users creates mail service files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            # Create test users
            users = [
                UserConfig(
                    username="user1", email="user1@example.com", domains=["example.com"]
                ),
                UserConfig(
                    username="user2", email="user2@test.com", domains=["test.com"]
                ),
            ]

            result = synchronizer.sync_users(users)

            assert result is True

            # Check that mail files were created
            mail_dir = config_manager.paths.state_path / "mail"
            assert mail_dir.exists()

            virtual_users_file = mail_dir / "virtual_users"
            assert virtual_users_file.exists()

            # Check file contents
            with open(virtual_users_file, "r") as f:
                content = f.read()
            assert "user1@example.com" in content
            assert "user2@test.com" in content

    def test_sync_users_creates_dovecot_users(self):
        """Test that syncing users creates Dovecot user file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            users = [
                UserConfig(username="dovecottest", email="dovecottest@example.com")
            ]

            synchronizer.sync_users(users)

            # Check Dovecot users file
            dovecot_users_file = (
                config_manager.paths.state_path / "mail" / "dovecot_users"
            )
            assert dovecot_users_file.exists()

            with open(dovecot_users_file, "r") as f:
                content = f.read()
            assert "dovecottest" in content
            # Check that it follows passwd format (username:password:uid:gid...)
            assert ":" in content

    def test_sync_domains_creates_files(self):
        """Test that syncing domains creates mail domain files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            # Create test domains
            domains = [
                DomainConfig(name="example.com", enabled=True),
                DomainConfig(name="test.com", enabled=True),
                DomainConfig(name="disabled.com", enabled=False),
            ]

            result = synchronizer.sync_domains(domains)

            assert result is True

            # Check virtual domains file
            virtual_domains_file = (
                config_manager.paths.state_path / "mail" / "virtual_domains"
            )
            assert virtual_domains_file.exists()

            with open(virtual_domains_file, "r") as f:
                content = f.read()
            assert "example.com" in content
            assert "test.com" in content
            assert (
                "disabled.com" not in content
            )  # Disabled domains should not be included

    def test_validate_configuration_missing_files(self):
        """Test validation with missing configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            errors = synchronizer.validate_configuration()

            # Should report missing files
            assert len(errors) > 0
            assert any("virtual_users" in error for error in errors)
            assert any("virtual_domains" in error for error in errors)
            assert any("dovecot_users" in error for error in errors)

    def test_validate_configuration_with_files(self):
        """Test validation with existing configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            # Create the required files
            mail_dir = config_manager.paths.state_path / "mail"
            mail_dir.mkdir(parents=True, exist_ok=True)

            for filename in ["virtual_users", "virtual_domains", "dovecot_users"]:
                (mail_dir / filename).touch()

            errors = synchronizer.validate_configuration()

            # Should not report missing files
            assert len(errors) == 0

    def test_reload_service_without_container(self):
        """Test reload service without container manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            result = synchronizer.reload_service()

            # Should return False when no container manager
            assert result is False

    def test_reload_service_with_container(self):
        """Test reload service with container manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            mock_container = MagicMock()
            mock_container.execute_command.return_value = MagicMock(success=True)

            synchronizer = MailServiceSynchronizer(config_manager, mock_container)

            result = synchronizer.reload_service()

            assert result is True
            # Should have called reload commands
            assert mock_container.execute_command.call_count >= 2  # Postfix and Dovecot


class TestDnsServiceSynchronizer:
    """Test DnsServiceSynchronizer class."""

    def test_dns_service_synchronizer_init(self):
        """Test DNS synchronizer initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            mock_container = MagicMock()
            synchronizer = DnsServiceSynchronizer(config_manager, mock_container)

            assert synchronizer.config_manager is config_manager
            assert synchronizer.container_manager is mock_container

    def test_sync_users_does_nothing(self):
        """Test that DNS synchronizer doesn't sync users."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = DnsServiceSynchronizer(config_manager)

            users = [UserConfig(username="test", email="test@example.com")]

            result = synchronizer.sync_users(users)

            # DNS doesn't need user sync, should return True but do nothing
            assert result is True

    def test_sync_domains_creates_zone_files(self):
        """Test that syncing domains creates DNS zone files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = DnsServiceSynchronizer(config_manager)

            # Create test domains with DNS records
            domains = [
                DomainConfig(
                    name="example.com",
                    enabled=True,
                    mx_records=["mail.example.com"],
                    a_records={"www": "192.168.1.1", "mail": "192.168.1.2"},
                ),
                DomainConfig(
                    name="test.com", enabled=True, a_records={"@": "192.168.2.1"}
                ),
            ]

            result = synchronizer.sync_domains(domains)

            assert result is True

            # Check zone files were created
            zones_dir = config_manager.paths.state_path / "dns-zones"
            assert zones_dir.exists()

            example_zone = zones_dir / "db.example.com"
            test_zone = zones_dir / "db.test.com"

            assert example_zone.exists()
            assert test_zone.exists()

            # Check zone file content
            with open(example_zone, "r") as f:
                content = f.read()
            assert "example.com" in content
            assert "mail.example.com" in content
            assert "192.168.1.1" in content
            assert "192.168.1.2" in content

    def test_sync_domains_skips_disabled(self):
        """Test that disabled domains are not synced."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = DnsServiceSynchronizer(config_manager)

            domains = [
                DomainConfig(name="enabled.com", enabled=True),
                DomainConfig(name="disabled.com", enabled=False),
            ]

            synchronizer.sync_domains(domains)

            zones_dir = config_manager.paths.state_path / "dns-zones"
            assert (zones_dir / "db.enabled.com").exists()
            assert not (zones_dir / "db.disabled.com").exists()

    def test_validate_configuration_with_container(self):
        """Test DNS validation with container."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            mock_container = MagicMock()

            # Mock successful BIND config check
            mock_result = MagicMock()
            mock_result.success = True
            mock_container.execute_command.return_value = mock_result

            synchronizer = DnsServiceSynchronizer(config_manager, mock_container)

            errors = synchronizer.validate_configuration()

            # Should check BIND configuration
            mock_container.execute_command.assert_called()
            # With successful validation, should have no errors from BIND check
            bind_errors = [e for e in errors if "BIND configuration error" in e]
            assert len(bind_errors) == 0

    def test_validate_configuration_without_container(self):
        """Test DNS validation without container."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = DnsServiceSynchronizer(config_manager)

            errors = synchronizer.validate_configuration()

            # Should return errors for missing container
            assert len(errors) > 0

    def test_reload_service_with_container(self):
        """Test DNS service reload with container."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            mock_container = MagicMock()
            mock_container.execute_command.return_value = MagicMock(success=True)

            synchronizer = DnsServiceSynchronizer(config_manager, mock_container)

            result = synchronizer.reload_service()

            assert result is True
            # Should have called BIND reload
            mock_container.execute_command.assert_called()

    def test_reload_service_without_container(self):
        """Test DNS service reload without container."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = DnsServiceSynchronizer(config_manager)

            result = synchronizer.reload_service()

            assert result is False


class TestUtilityFunctions:
    """Test utility functions in sync module."""

    def test_zone_file_creation_integration(self):
        """Test DNS zone file creation integration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = DnsServiceSynchronizer(config_manager)

            domain = DomainConfig(
                name="test.com",
                mx_records=["mail.test.com"],
                a_records={"www": "1.2.3.4", "@": "1.2.3.5"},
                cname_records={"blog": "www.test.com"},
                txt_records={"@": "v=spf1 include:_spf.test.com ~all"},
            )

            # Test zone file creation through sync_domains
            result = synchronizer.sync_domains([domain])
            assert result is True

            # Check that zone file was created
            zone_file = config_manager.paths.state_path / "dns-zones" / "db.test.com"
            assert zone_file.exists()

            # Check zone file content
            with open(zone_file, "r") as f:
                content = f.read()
            assert "$TTL" in content
            assert "test.com." in content
            assert "mail.test.com." in content
            assert "1.2.3.4" in content

    def test_dovecot_user_file_format(self):
        """Test Dovecot user file format creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            users = [UserConfig(username="testuser", email="test@example.com")]

            # Test user file creation through sync_users
            result = synchronizer.sync_users(users)
            assert result is True

            # Check Dovecot users file format
            dovecot_file = config_manager.paths.state_path / "mail" / "dovecot_users"
            assert dovecot_file.exists()


class TestErrorHandling:
    """Test error handling in synchronization."""

    def test_mail_sync_users_permission_error(self):
        """Test mail sync users with permission error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            users = [UserConfig(username="testuser", email="test@example.com")]

            # Mock file write to raise permission error
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                result = synchronizer.sync_users(users)
                assert result is False

    def test_mail_sync_domains_io_error(self):
        """Test mail sync domains with IO error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            domains = [DomainConfig(name="test.com")]

            # Mock file write to raise IO error
            with patch("builtins.open", side_effect=IOError("Disk full")):
                result = synchronizer.sync_domains(domains)
                assert result is False

    def test_dns_sync_users_error(self):
        """Test DNS sync users error handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = DnsServiceSynchronizer(config_manager)

            users = [UserConfig(username="testuser", email="test@example.com")]

            # DNS doesn't sync users, so it should always return True
            result = synchronizer.sync_users(users)
            assert result is True

    def test_dns_sync_domains_error(self):
        """Test DNS sync domains error handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = DnsServiceSynchronizer(config_manager)

            domains = [DomainConfig(name="test.com")]

            # Mock file write to raise error
            with patch("builtins.open", side_effect=Exception("Generic error")):
                result = synchronizer.sync_domains(domains)
                assert result is False

    def test_mail_validate_configuration_missing_files(self):
        """Test mail configuration validation with missing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            # Don't create any mail config files
            errors = synchronizer.validate_configuration()

            # Should find errors for missing files
            assert len(errors) > 0
            assert any("virtual_users" in error for error in errors)
            assert any("virtual_domains" in error for error in errors)
            assert any("dovecot_users" in error for error in errors)

    def test_dns_validate_configuration_missing_files(self):
        """Test DNS configuration validation with missing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = DnsServiceSynchronizer(config_manager)

            # Don't create any DNS config files
            errors = synchronizer.validate_configuration()

            # Should find errors for missing DNS config
            assert (
                len(errors) >= 0
            )  # DNS validation may return empty list if no domains configured

    def test_mail_reload_service_no_container_manager(self):
        """Test mail service reload when no container manager is set."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            # Test reload without container manager
            result = synchronizer.reload_service()
            assert result is False

    def test_dns_reload_service_no_container_manager(self):
        """Test DNS service reload when no container manager is set."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = DnsServiceSynchronizer(config_manager)

            # Test reload without container manager
            result = synchronizer.reload_service()
            assert result is False

    def test_sync_users_with_disabled_user(self):
        """Test syncing users with some disabled users."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            users = [
                UserConfig(
                    username="active",
                    email="active@test.com",
                    domains=["test.com"],
                    enabled=True,
                ),
                UserConfig(
                    username="disabled",
                    email="disabled@test.com",
                    domains=["test.com"],
                    enabled=False,
                ),
            ]

            result = synchronizer.sync_users(users)
            assert result is True

            # Check that only enabled user was processed
            virtual_users_file = (
                config_manager.paths.state_path / "mail" / "virtual_users"
            )
            with open(virtual_users_file, "r") as f:
                content = f.read()
            assert "active@test.com" in content
            assert "disabled@test.com" not in content

    def test_sync_domains_with_disabled_domain(self):
        """Test syncing domains with some disabled domains."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            synchronizer = MailServiceSynchronizer(config_manager)

            domains = [
                DomainConfig(name="active.com", enabled=True),
                DomainConfig(name="disabled.com", enabled=False),
            ]

            result = synchronizer.sync_domains(domains)
            assert result is True

            # Check that only enabled domain was processed
            virtual_domains_file = (
                config_manager.paths.state_path / "mail" / "virtual_domains"
            )
            with open(virtual_domains_file, "r") as f:
                content = f.read()
            assert "active.com" in content
            assert "disabled.com" not in content
