"""Unit tests for configuration manager."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from net_servers.config.manager import ConfigurationManager
from net_servers.config.schemas import (
    DomainConfig,
    DomainsConfig,
    GlobalConfig,
    ServicesConfig,
    UserConfig,
    UsersConfig,
)


class TestConfigurationManager:
    """Test ConfigurationManager class."""

    def test_configuration_manager_init(self):
        """Test configuration manager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            assert config_manager.paths.base_path == Path(temp_dir)
            assert config_manager.paths.config_path == Path(temp_dir) / "config"

            # Check that directories were created
            assert config_manager.paths.config_path.exists()
            assert config_manager.paths.state_path.exists()

    def test_configuration_manager_default_path(self):
        """Test configuration manager with default path."""
        # This should work without errors even if /data doesn't exist
        # since we're just testing the path setup
        with patch("net_servers.config.schemas.ConfigurationPaths.ensure_directories"):
            config_manager = ConfigurationManager()
            assert config_manager.paths.base_path == Path("/data")

    def test_global_config_property(self):
        """Test global config property loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Create a test global config file
            global_config_path = config_manager.paths.config_path / "global.yaml"
            test_config = {
                "system": {
                    "domain": "test.example.com",
                    "admin_email": "admin@test.example.com",
                }
            }

            with open(global_config_path, "w") as f:
                yaml.dump(test_config, f)

            # Test loading
            global_config = config_manager.global_config
            assert isinstance(global_config, GlobalConfig)
            assert global_config.system.domain == "test.example.com"
            assert global_config.system.admin_email == "admin@test.example.com"

            # Test caching - should return same instance
            global_config2 = config_manager.global_config
            assert global_config is global_config2

    def test_global_config_missing_file(self):
        """Test global config property with missing file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Test loading non-existent file returns defaults
            global_config = config_manager.global_config
            assert isinstance(global_config, GlobalConfig)
            assert global_config.system.domain == "local.dev"  # Default

    def test_users_config_property(self):
        """Test users config property loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Create a test users config file
            users_config_path = config_manager.paths.config_path / "users.yaml"
            test_config = {
                "users": [
                    {
                        "username": "testuser",
                        "email": "testuser@example.com",
                        "domains": ["example.com"],
                        "roles": ["user"],
                    }
                ]
            }

            with open(users_config_path, "w") as f:
                yaml.dump(test_config, f)

            # Test loading
            users_config = config_manager.users_config
            assert isinstance(users_config, UsersConfig)
            assert len(users_config.users) == 1
            assert users_config.users[0].username == "testuser"
            assert users_config.users[0].email == "testuser@example.com"

    def test_domains_config_property(self):
        """Test domains config property loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Create a test domains config file
            domains_config_path = config_manager.paths.config_path / "domains.yaml"
            test_config = {
                "domains": [
                    {
                        "name": "example.com",
                        "enabled": True,
                        "mx_records": ["mail.example.com"],
                        "a_records": {"www": "192.168.1.1"},
                    }
                ]
            }

            with open(domains_config_path, "w") as f:
                yaml.dump(test_config, f)

            # Test loading
            domains_config = config_manager.domains_config
            assert isinstance(domains_config, DomainsConfig)
            assert len(domains_config.domains) == 1
            assert domains_config.domains[0].name == "example.com"
            assert domains_config.domains[0].a_records["www"] == "192.168.1.1"

    def test_services_config_property(self):
        """Test services config property loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Create services directory and config file
            services_dir = config_manager.paths.config_path / "services"
            services_dir.mkdir(exist_ok=True)
            services_config_path = services_dir / "services.yaml"

            test_config = {
                "mail": {"virtual_domains": ["example.com", "test.com"]},
                "dns": {"forwarders": ["1.1.1.1", "1.0.0.1"]},
            }

            with open(services_config_path, "w") as f:
                yaml.dump(test_config, f)

            # Test loading
            services_config = config_manager.services_config
            assert isinstance(services_config, ServicesConfig)
            assert services_config.mail.virtual_domains == ["example.com", "test.com"]
            assert services_config.dns.forwarders == ["1.1.1.1", "1.0.0.1"]

    def test_reload_config(self):
        """Test configuration reloading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Load initial config
            global_config1 = config_manager.global_config

            # Reload config
            config_manager.reload_config()

            # Load config again - should be different instance
            global_config2 = config_manager.global_config
            assert global_config1 is not global_config2

    def test_save_global_config(self):
        """Test saving global configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Create test config
            test_config = GlobalConfig(
                system={"domain": "save-test.com", "admin_email": "admin@save-test.com"}
            )

            # Save config
            config_manager.save_global_config(test_config)

            # Verify file was created
            config_file = config_manager.paths.config_path / "global.yaml"
            assert config_file.exists()

            # Verify content
            with open(config_file, "r") as f:
                data = yaml.safe_load(f)
            assert data["system"]["domain"] == "save-test.com"

            # Verify cached config was updated
            assert config_manager._global_config is test_config

    def test_save_users_config(self):
        """Test saving users configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Create test config
            user = UserConfig(
                username="savetest",
                email="savetest@example.com",
                domains=["example.com"],
            )
            test_config = UsersConfig(users=[user])

            # Save config
            config_manager.save_users_config(test_config)

            # Verify file was created
            config_file = config_manager.paths.config_path / "users.yaml"
            assert config_file.exists()

            # Verify content
            with open(config_file, "r") as f:
                data = yaml.safe_load(f)
            assert len(data["users"]) == 1
            assert data["users"][0]["username"] == "savetest"

    def test_save_domains_config(self):
        """Test saving domains configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Create test config
            domain = DomainConfig(
                name="save-test.com",
                mx_records=["mail.save-test.com"],
                a_records={"www": "1.2.3.4"},
            )
            test_config = DomainsConfig(domains=[domain])

            # Save config
            config_manager.save_domains_config(test_config)

            # Verify file was created
            config_file = config_manager.paths.config_path / "domains.yaml"
            assert config_file.exists()

            # Verify content
            with open(config_file, "r") as f:
                data = yaml.safe_load(f)
            assert len(data["domains"]) == 1
            assert data["domains"][0]["name"] == "save-test.com"

    def test_save_services_config(self):
        """Test saving services configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Create test config
            test_config = ServicesConfig()
            test_config.mail.virtual_domains = ["save-test.com"]
            test_config.dns.forwarders = ["8.8.8.8"]

            # Save config
            config_manager.save_services_config(test_config)

            # Verify file was created
            services_dir = config_manager.paths.config_path / "services"
            config_file = services_dir / "services.yaml"
            assert config_file.exists()

            # Verify content
            with open(config_file, "r") as f:
                data = yaml.safe_load(f)
            assert data["mail"]["virtual_domains"] == ["save-test.com"]
            assert data["dns"]["forwarders"] == ["8.8.8.8"]

    def test_get_container_volumes(self):
        """Test getting container volumes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Test development mode (default)
            volumes = config_manager.get_container_volumes(development_mode=True)

            # Calculate expected volumes (project root and environments.yaml if exists)
            import os
            from pathlib import Path

            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(current_file))
            code_host_path = str(Path(project_root).resolve())

            expected_volume_count = 4  # config, state, logs, code
            environments_file = os.path.join(code_host_path, "environments.yaml")
            if os.path.exists(environments_file):
                expected_volume_count = 5  # +environments.yaml

            assert len(volumes) == expected_volume_count

            # Check volume types
            volume_paths = [(v.host_path, v.container_path) for v in volumes]

            expected_paths = [
                (str(Path(f"{temp_dir}/config").resolve()), "/data/config"),
                (str(Path(f"{temp_dir}/state").resolve()), "/data/state"),
                (str(Path(f"{temp_dir}/logs").resolve()), "/data/logs"),
                (code_host_path, "/data/code"),
            ]

            if os.path.exists(environments_file):
                expected_paths.append((environments_file, "/data/environments.yaml"))

            for expected in expected_paths:
                assert expected in volume_paths

            # All should be read-write in development mode except environments.yaml
            for volume in volumes:
                if volume.container_path == "/data/environments.yaml":
                    assert volume.read_only  # environments.yaml is read-only
                else:
                    assert not volume.read_only

    def test_get_container_volumes_production_mode(self):
        """Test getting container volumes in production mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Test production mode
            volumes = config_manager.get_container_volumes(development_mode=False)

            # All volumes should still be read-write in current implementation
            # except environments.yaml (This test documents current behavior)
            for volume in volumes:
                if volume.container_path == "/data/environments.yaml":
                    assert volume.read_only  # environments.yaml is read-only
                else:
                    assert not volume.read_only

    def test_get_container_environment_mail(self):
        """Test getting environment variables for mail service."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Set up global config with custom values
            config_manager.save_global_config(
                GlobalConfig(
                    system={
                        "domain": "mail-test.com",
                        "admin_email": "admin@mail-test.com",
                    }
                )
            )

            # Set up services config
            services_config = ServicesConfig()
            services_config.mail.virtual_domains = ["mail-test.com", "example.com"]
            services_config.mail.relay_domains = ["relay.com"]
            config_manager.save_services_config(services_config)

            # Get environment
            env = config_manager.get_container_environment("mail")

            # Check common variables
            assert env["SERVICE_NAME"] == "mail"
            assert env["DOMAIN"] == "mail-test.com"
            assert env["ADMIN_EMAIL"] == "admin@mail-test.com"
            assert env["CONFIG_PATH"] == "/data/config"
            assert env["STATE_PATH"] == "/data/state"
            assert env["LOGS_PATH"] == "/data/logs"

            # Check mail-specific variables
            assert env["VIRTUAL_DOMAINS"] == "mail-test.com,example.com"
            assert env["RELAY_DOMAINS"] == "relay.com"

    def test_get_container_environment_dns(self):
        """Test getting environment variables for DNS service."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Set up services config
            services_config = ServicesConfig()
            services_config.dns.forwarders = ["1.1.1.1", "8.8.8.8"]
            services_config.dns.zone_file_path = "/custom/zones"
            config_manager.save_services_config(services_config)

            # Get environment
            env = config_manager.get_container_environment("dns")

            # Check DNS-specific variables
            assert env["SERVICE_NAME"] == "dns"
            assert env["DNS_FORWARDERS"] == "1.1.1.1,8.8.8.8"
            assert env["ZONE_FILE_PATH"] == "/custom/zones"

    def test_get_container_environment_apache(self):
        """Test getting environment variables for Apache service."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Set up services config
            services_config = ServicesConfig()
            services_config.apache.document_root = "/custom/www"
            services_config.apache.server_admin = "webmaster@example.com"
            config_manager.save_services_config(services_config)

            # Get environment
            env = config_manager.get_container_environment("apache")

            # Check Apache-specific variables
            assert env["SERVICE_NAME"] == "apache"
            assert env["DOCUMENT_ROOT"] == "/custom/www"
            assert env["SERVER_ADMIN"] == "webmaster@example.com"

    def test_enhance_container_config(self):
        """Test enhancing container configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            from net_servers.actions.container import ContainerConfig

            # Create basic container config
            container_config = ContainerConfig(
                image_name="test-image", dockerfile="Dockerfile", port=8080
            )

            # Enhance for mail service
            enhanced_config = config_manager.enhance_container_config(
                container_config, "mail", development_mode=True
            )

            # Check volumes were added
            assert len(enhanced_config.volumes) > 0
            volume_paths = [v.container_path for v in enhanced_config.volumes]
            assert "/data/config" in volume_paths
            assert "/data/state" in volume_paths

            # Check environment was added
            assert "SERVICE_NAME" in enhanced_config.environment
            assert enhanced_config.environment["SERVICE_NAME"] == "mail"

            # Check state paths were added
            assert "/data/state/mailboxes" in enhanced_config.state_paths
            assert "/data/state/mail" in enhanced_config.state_paths

    def test_enhance_container_config_dns(self):
        """Test enhancing container configuration for DNS service."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            from net_servers.actions.container import ContainerConfig

            container_config = ContainerConfig(image_name="dns-image")
            enhanced_config = config_manager.enhance_container_config(
                container_config, "dns"
            )

            # Check DNS-specific state paths
            assert "/data/state/dns-zones" in enhanced_config.state_paths
            assert "/data/state/dns" in enhanced_config.state_paths

    def test_enhance_container_config_apache(self):
        """Test enhancing container configuration for Apache service."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            from net_servers.actions.container import ContainerConfig

            container_config = ContainerConfig(image_name="apache-image")
            enhanced_config = config_manager.enhance_container_config(
                container_config, "apache"
            )

            # Check Apache-specific state paths
            assert "/data/state/certificates" in enhanced_config.state_paths
            assert "/data/state/apache" in enhanced_config.state_paths

    def test_initialize_default_configs(self):
        """Test initializing default configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Initialize default configs
            config_manager.initialize_default_configs()

            # Check that config files were created
            assert (config_manager.paths.config_path / "global.yaml").exists()
            assert (config_manager.paths.config_path / "users.yaml").exists()
            assert (config_manager.paths.config_path / "domains.yaml").exists()
            assert (
                config_manager.paths.config_path / "services" / "services.yaml"
            ).exists()

            # Check default global config
            global_config = config_manager.global_config
            assert global_config.system.domain == "local.dev"

            # Check default users config (should have admin user)
            users_config = config_manager.users_config
            assert len(users_config.users) == 1
            assert users_config.users[0].username == "admin"
            assert users_config.users[0].roles == ["admin"]

            # Check default domains config
            domains_config = config_manager.domains_config
            assert len(domains_config.domains) == 1
            assert domains_config.domains[0].name == "local.dev"

            # Check default services config
            services_config = config_manager.services_config
            assert "local.dev" in services_config.mail.virtual_domains

    def test_initialize_default_configs_existing_files(self):
        """Test that initialize_default_configs doesn't overwrite existing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Create custom global config
            custom_config = GlobalConfig(
                system={"domain": "existing.com", "admin_email": "custom@existing.com"}
            )
            config_manager.save_global_config(custom_config)

            # Initialize defaults (should not overwrite)
            config_manager.initialize_default_configs()

            # Check that existing config was preserved
            global_config = config_manager.global_config
            assert global_config.system.domain == "existing.com"
            assert global_config.system.admin_email == "custom@existing.com"

    def test_validate_configuration_success(self):
        """Test configuration validation with valid configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Set up valid configuration
            config_manager.initialize_default_configs()

            # Validate
            errors = config_manager.validate_configuration()
            assert errors == []

    def test_validate_configuration_user_domain_mismatch(self):
        """Test configuration validation with user referencing unknown domain."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Set up configuration with domain mismatch
            config_manager.initialize_default_configs()

            # Add user with unknown domain
            users_config = config_manager.users_config
            bad_user = UserConfig(
                username="baduser",
                email="bad@unknown.com",
                domains=["unknown.com"],  # This domain doesn't exist
            )
            users_config.users.append(bad_user)
            config_manager.save_users_config(users_config)

            # Validate
            errors = config_manager.validate_configuration()
            assert len(errors) > 0
            assert any("unknown domain" in error for error in errors)

    def test_validate_configuration_service_domain_mismatch(self):
        """Test configuration validation with service referencing unknown domain."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Set up configuration
            config_manager.initialize_default_configs()

            # Add unknown virtual domain to mail service
            services_config = config_manager.services_config
            services_config.mail.virtual_domains.append("unknown-service.com")
            config_manager.save_services_config(services_config)

            # Validate
            errors = config_manager.validate_configuration()
            assert len(errors) > 0
            assert any("unknown virtual domain" in error for error in errors)

    def test_validate_configuration_invalid_email(self):
        """Test configuration validation with invalid email."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Set up configuration
            config_manager.initialize_default_configs()

            # Manually create user with invalid email (bypass Pydantic validation)
            users_config = config_manager.users_config
            # Create user dict directly to bypass validation during creation
            users_config.users[0].email = "invalid-email-no-at-symbol"
            config_manager.save_users_config(users_config)

            # Clear cache and reload to get the invalid data
            config_manager.reload_config()

            # Validate
            errors = config_manager.validate_configuration()
            assert len(errors) > 0
            assert any("Invalid email" in error for error in errors)

    def test_validate_configuration_exception_handling(self):
        """Test that validation handles exceptions gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)

            # Create corrupted config file to trigger exception
            domains_file = config_manager.paths.config_path / "domains.yaml"
            with open(domains_file, "w") as f:
                f.write("invalid: yaml: [unclosed list")

            # This should trigger an exception during YAML loading
            errors = config_manager.validate_configuration()
            assert len(errors) > 0
            assert any("Configuration validation error" in error for error in errors)
