"""Unit tests for configuration schemas and validation."""

import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from net_servers.config.schemas import (
    ConfigurationPaths,
    DomainConfig,
    DomainsConfig,
    GlobalConfig,
    SystemConfig,
    UserConfig,
    UsersConfig,
    get_default_volumes,
    load_yaml_config,
    save_yaml_config,
)


class TestSystemConfig:
    """Test SystemConfig schema."""

    def test_system_config_defaults(self):
        """Test that SystemConfig has proper defaults."""
        config = SystemConfig()
        assert config.domain == "local.dev"
        assert config.admin_email == "admin@local.dev"
        assert config.timezone == "UTC"

    def test_system_config_custom_values(self):
        """Test SystemConfig with custom values."""
        config = SystemConfig(
            domain="example.com",
            admin_email="admin@example.com",
            timezone="America/New_York",
        )
        assert config.domain == "example.com"
        assert config.admin_email == "admin@example.com"
        assert config.timezone == "America/New_York"


class TestGlobalConfig:
    """Test GlobalConfig schema."""

    def test_global_config_defaults(self):
        """Test that GlobalConfig creates proper defaults."""
        config = GlobalConfig()
        assert config.system.domain == "local.dev"
        assert config.networks.internal == "172.20.0.0/16"
        assert config.security.tls_enabled is True

    def test_global_config_nested_values(self):
        """Test GlobalConfig with nested custom values."""
        config = GlobalConfig(
            system={"domain": "test.com", "admin_email": "test@test.com"},
            networks={"internal": "10.0.0.0/16"},
            security={"tls_enabled": False},
        )
        assert config.system.domain == "test.com"
        assert config.system.admin_email == "test@test.com"
        assert config.networks.internal == "10.0.0.0/16"
        assert config.security.tls_enabled is False


class TestUserConfig:
    """Test UserConfig schema and validation."""

    def test_user_config_valid(self):
        """Test valid user configuration."""
        user = UserConfig(
            username="testuser",
            email="testuser@example.com",
            domains=["example.com"],
            roles=["user"],
            mailbox_quota="500M",
        )
        assert user.username == "testuser"
        assert user.email == "testuser@example.com"
        assert user.domains == ["example.com"]
        assert user.roles == ["user"]
        assert user.mailbox_quota == "500M"
        assert user.enabled is True

    def test_user_config_defaults(self):
        """Test user configuration with defaults."""
        user = UserConfig(username="testuser", email="test@example.com")
        assert user.domains == []
        assert user.roles == ["user"]
        assert user.mailbox_quota == "500M"
        assert user.enabled is True

    def test_user_config_invalid_email(self):
        """Test user configuration with invalid email."""
        with pytest.raises(ValidationError) as exc_info:
            UserConfig(username="testuser", email="invalid-email")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "value_error"
        assert "Invalid email address" in str(errors[0]["ctx"])

    def test_user_config_multiple_domains(self):
        """Test user configuration with multiple domains."""
        user = UserConfig(
            username="testuser",
            email="test@example.com",
            domains=["example.com", "test.com", "local.dev"],
        )
        assert len(user.domains) == 3
        assert "example.com" in user.domains
        assert "test.com" in user.domains
        assert "local.dev" in user.domains

    def test_user_config_multiple_roles(self):
        """Test user configuration with multiple roles."""
        user = UserConfig(
            username="admin",
            email="admin@example.com",
            roles=["admin", "user", "maintainer"],
        )
        assert len(user.roles) == 3
        assert "admin" in user.roles
        assert "user" in user.roles
        assert "maintainer" in user.roles


class TestUsersConfig:
    """Test UsersConfig schema."""

    def test_users_config_empty(self):
        """Test empty users configuration."""
        config = UsersConfig()
        assert config.users == []

    def test_users_config_with_users(self):
        """Test users configuration with multiple users."""
        users = [
            UserConfig(username="user1", email="user1@example.com"),
            UserConfig(username="user2", email="user2@example.com", roles=["admin"]),
        ]
        config = UsersConfig(users=users)
        assert len(config.users) == 2
        assert config.users[0].username == "user1"
        assert config.users[1].username == "user2"
        assert config.users[1].roles == ["admin"]


class TestDomainConfig:
    """Test DomainConfig schema."""

    def test_domain_config_minimal(self):
        """Test minimal domain configuration."""
        domain = DomainConfig(name="example.com")
        assert domain.name == "example.com"
        assert domain.enabled is True
        assert domain.mx_records == []
        assert domain.a_records == {}
        assert domain.cname_records == {}
        assert domain.txt_records == {}
        assert domain.srv_records == []

    def test_domain_config_complete(self):
        """Test complete domain configuration."""
        domain = DomainConfig(
            name="example.com",
            enabled=True,
            mx_records=["mail.example.com", "mail2.example.com"],
            a_records={"www": "192.168.1.1", "mail": "192.168.1.2"},
            cname_records={"blog": "www.example.com"},
            txt_records={"_dmarc": "v=DMARC1; p=none;"},
            srv_records=[
                {
                    "name": "_sip._tcp",
                    "priority": 10,
                    "weight": 0,
                    "port": 5060,
                    "target": "sip.example.com",
                }
            ],
        )
        assert domain.name == "example.com"
        assert domain.enabled is True
        assert len(domain.mx_records) == 2
        assert domain.a_records["www"] == "192.168.1.1"
        assert domain.cname_records["blog"] == "www.example.com"
        assert "_dmarc" in domain.txt_records
        assert len(domain.srv_records) == 1

    def test_domain_config_disabled(self):
        """Test disabled domain configuration."""
        domain = DomainConfig(name="disabled.com", enabled=False)
        assert domain.name == "disabled.com"
        assert domain.enabled is False


class TestDomainsConfig:
    """Test DomainsConfig schema."""

    def test_domains_config_empty(self):
        """Test empty domains configuration."""
        config = DomainsConfig()
        assert config.domains == []

    def test_domains_config_with_domains(self):
        """Test domains configuration with multiple domains."""
        domains = [
            DomainConfig(name="example.com"),
            DomainConfig(name="test.com", enabled=False),
        ]
        config = DomainsConfig(domains=domains)
        assert len(config.domains) == 2
        assert config.domains[0].name == "example.com"
        assert config.domains[0].enabled is True
        assert config.domains[1].name == "test.com"
        assert config.domains[1].enabled is False


class TestConfigurationPaths:
    """Test ConfigurationPaths dataclass."""

    def test_configuration_paths_defaults(self):
        """Test default configuration paths."""
        paths = ConfigurationPaths()
        assert paths.base_path == Path("/data")
        assert paths.config_path == Path("/data/config")
        assert paths.state_path == Path("/data/state")
        assert paths.logs_path == Path("/data/logs")
        assert paths.code_path == Path("/data/code")

    def test_configuration_paths_custom_base(self):
        """Test configuration paths with custom base path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = ConfigurationPaths(base_path=Path(temp_dir))
            assert paths.base_path == Path(temp_dir)
            assert paths.config_path == Path(temp_dir) / "config"
            assert paths.state_path == Path(temp_dir) / "state"
            assert paths.logs_path == Path(temp_dir) / "logs"
            assert paths.code_path == Path(temp_dir) / "code"

    def test_ensure_directories_creates_structure(self):
        """Test that ensure_directories creates the expected structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = ConfigurationPaths(base_path=Path(temp_dir))
            paths.ensure_directories()

            # Check main directories
            assert paths.config_path.exists()
            assert paths.state_path.exists()
            assert paths.logs_path.exists()
            assert paths.code_path.exists()

            # Check service directories
            assert (paths.state_path / "mail").exists()
            assert (paths.state_path / "dns").exists()
            assert (paths.state_path / "apache").exists()
            assert (paths.logs_path / "mail").exists()
            assert (paths.logs_path / "dns").exists()
            assert (paths.logs_path / "apache").exists()

            # Check specialized directories
            assert (paths.config_path / "services").exists()
            assert (paths.state_path / "mailboxes").exists()
            assert (paths.state_path / "dns-zones").exists()
            assert (paths.state_path / "certificates").exists()


class TestYamlHelpers:
    """Test YAML loading and saving helpers."""

    def test_load_yaml_config_missing_file(self):
        """Test loading config from non-existent file returns defaults."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "missing.yaml"
            config = load_yaml_config(file_path, GlobalConfig)
            assert isinstance(config, GlobalConfig)
            assert config.system.domain == "local.dev"  # Default value

    def test_load_yaml_config_valid_file(self):
        """Test loading config from valid YAML file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "config.yaml"

            # Create test config
            test_data = {
                "system": {
                    "domain": "test.example.com",
                    "admin_email": "admin@test.example.com",
                }
            }

            with open(file_path, "w") as f:
                yaml.dump(test_data, f)

            config = load_yaml_config(file_path, GlobalConfig)
            assert isinstance(config, GlobalConfig)
            assert config.system.domain == "test.example.com"
            assert config.system.admin_email == "admin@test.example.com"

    def test_load_yaml_config_invalid_yaml(self):
        """Test loading config from invalid YAML file raises error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid.yaml"

            # Create invalid YAML
            with open(file_path, "w") as f:
                f.write("invalid: yaml: content: [\n")

            with pytest.raises(ValueError, match="Failed to load config"):
                load_yaml_config(file_path, GlobalConfig)

    def test_save_yaml_config(self):
        """Test saving configuration to YAML file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "output.yaml"

            config = GlobalConfig(
                system={"domain": "save-test.com"}, networks={"internal": "10.1.0.0/16"}
            )

            save_yaml_config(config, file_path)

            # Verify file was created
            assert file_path.exists()

            # Verify content
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)

            assert data["system"]["domain"] == "save-test.com"
            assert data["networks"]["internal"] == "10.1.0.0/16"

    def test_save_yaml_config_creates_parent_dirs(self):
        """Test that save_yaml_config creates parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "nested" / "dirs" / "config.yaml"

            config = GlobalConfig()
            save_yaml_config(config, file_path)

            assert file_path.exists()
            assert file_path.parent.exists()


class TestVolumeHelpers:
    """Test volume configuration helpers."""

    def test_get_default_volumes_default_path(self):
        """Test get_default_volumes with default path."""
        volumes = get_default_volumes()

        expected_volumes = [
            ("/data/config", "/data/config", False),
            ("/data/state", "/data/state", False),
            ("/data/logs", "/data/logs", False),
            ("/data/code", "/data/code", False),
        ]

        assert volumes == expected_volumes

    def test_get_default_volumes_custom_path(self):
        """Test get_default_volumes with custom base path."""
        from pathlib import Path

        custom_base = "/tmp/test-data"
        volumes = get_default_volumes(custom_base)

        expected_volumes = [
            (str(Path("/tmp/test-data/config").resolve()), "/data/config", False),
            (str(Path("/tmp/test-data/state").resolve()), "/data/state", False),
            (str(Path("/tmp/test-data/logs").resolve()), "/data/logs", False),
            (str(Path("/tmp/test-data/code").resolve()), "/data/code", False),
        ]

        assert volumes == expected_volumes
