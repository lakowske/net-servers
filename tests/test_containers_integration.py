"""Integration tests for container configuration with environments."""

from unittest.mock import Mock, patch

import pytest

from net_servers.config.containers import (
    ENVIRONMENT_PORT_MAPPINGS,
    get_container_config,
)


class TestGetContainerConfigIntegration:
    """Test container configuration integration with environments."""

    def test_get_container_config_basic(self):
        """Test basic container config retrieval."""
        config = get_container_config("apache", use_config_manager=False)
        assert config.image_name == "net-servers-apache"
        assert config.container_name == "net-servers-apache-default"

    def test_get_container_config_unknown_container(self):
        """Test error handling for unknown container."""
        with pytest.raises(ValueError, match="Unknown container config"):
            get_container_config("unknown", use_config_manager=False)

    def test_get_container_config_predefined_environment(self):
        """Test container config with predefined environment."""
        config = get_container_config(
            "apache", environment_name="development", use_config_manager=False
        )
        assert config.container_name == "net-servers-apache-development"
        # Should use development port mappings
        assert any(pm.host_port == 8080 for pm in config.port_mappings)

    def test_get_container_config_unknown_environment_fallback(self):
        """Test container config with unknown environment falls back to development."""
        config = get_container_config(
            "apache", environment_name="unknown-env", use_config_manager=False
        )
        assert config.container_name == "net-servers-apache-unknown-env"
        # Should fall back to development port mappings
        assert any(pm.host_port == 8080 for pm in config.port_mappings)

    @patch("net_servers.cli_environments._get_config_manager")
    def test_get_container_config_with_config_manager_error(self, mock_get_manager):
        """Test config manager error handling."""
        mock_get_manager.side_effect = RuntimeError("Config error")

        with pytest.raises(
            RuntimeError, match="Failed to load environment configuration"
        ):
            get_container_config("apache", use_config_manager=True)

    @patch("net_servers.cli_environments._get_config_manager")
    def test_get_container_config_with_environment_port_mappings(
        self, mock_get_manager
    ):
        """Test container config using environment-stored port mappings."""
        # Mock environment with custom port mappings
        mock_env = Mock()
        mock_env.port_mappings = {
            "apache": [
                {"host_port": 9999, "container_port": 80, "protocol": "tcp"},
                {"host_port": 9998, "container_port": 443, "protocol": "tcp"},
            ]
        }

        mock_manager = Mock()
        mock_manager.get_current_environment.return_value = mock_env
        mock_get_manager.return_value = mock_manager

        config = get_container_config(
            "apache", environment_name="test", use_config_manager=True
        )

        # Should use custom port mappings from environment
        assert config.container_name == "net-servers-apache-test"
        assert any(pm.host_port == 9999 for pm in config.port_mappings)
        assert any(pm.host_port == 9998 for pm in config.port_mappings)

    @patch("net_servers.cli_environments._get_config_manager")
    def test_get_container_config_environment_without_port_mappings(
        self, mock_get_manager
    ):
        """Test container config when environment has no port mappings."""
        # Mock environment without port mappings
        mock_env = Mock()
        mock_env.port_mappings = {}

        mock_manager = Mock()
        mock_manager.get_current_environment.return_value = mock_env
        mock_get_manager.return_value = mock_manager

        config = get_container_config(
            "apache", environment_name="testing", use_config_manager=True
        )

        # Should fall back to predefined mappings (testing environment)
        assert config.container_name == "net-servers-apache-testing"
        # Should use testing environment ports
        expected_port = ENVIRONMENT_PORT_MAPPINGS["testing"]["apache"][0].host_port
        assert any(pm.host_port == expected_port for pm in config.port_mappings)

    def test_get_container_config_all_services(self):
        """Test container config retrieval for all services."""
        services = ["apache", "mail", "dns"]
        for service in services:
            config = get_container_config(service, use_config_manager=False)
            assert config.image_name == f"net-servers-{service}"
            assert config.container_name == f"net-servers-{service}-default"
            assert len(config.port_mappings) > 0

    def test_get_container_config_basic_all_services(self):
        """Test that all services return valid basic configs."""
        services = ["apache", "mail", "dns"]
        for service in services:
            config = get_container_config(
                service, use_config_manager=False, environment_name="development"
            )
            assert config.image_name == f"net-servers-{service}"
            assert config.container_name == f"net-servers-{service}-development"
            assert len(config.port_mappings) > 0


class TestEnvironmentPortMappingsData:
    """Test the predefined environment port mappings data structure."""

    def test_environment_port_mappings_structure(self):
        """Test that all required environments and services are defined."""
        required_environments = [
            "default",
            "development",
            "testing",
            "staging",
            "production",
        ]
        required_services = ["apache", "mail", "dns"]

        for env in required_environments:
            assert env in ENVIRONMENT_PORT_MAPPINGS, f"Missing environment: {env}"

            for service in required_services:
                assert (
                    service in ENVIRONMENT_PORT_MAPPINGS[env]
                ), f"Missing service {service} in {env}"

                port_mappings = ENVIRONMENT_PORT_MAPPINGS[env][service]
                assert (
                    len(port_mappings) > 0
                ), f"No port mappings for {service} in {env}"

                for pm in port_mappings:
                    assert hasattr(
                        pm, "host_port"
                    ), f"Missing host_port in {service}/{env}"
                    assert hasattr(
                        pm, "container_port"
                    ), f"Missing container_port in {service}/{env}"

    def test_port_mapping_uniqueness_within_environment(self):
        """Test that host ports are unique within each environment."""
        for env_name, env_mappings in ENVIRONMENT_PORT_MAPPINGS.items():
            used_ports = set()

            for service_name, port_mappings in env_mappings.items():
                for pm in port_mappings:
                    # DNS can use same port for UDP and TCP, so create unique key
                    port_key = (pm.host_port, getattr(pm, "protocol", "tcp"))
                    if service_name == "dns" and pm.container_port == 53:
                        # Allow DNS to reuse port 53 for UDP/TCP
                        port_key = (pm.host_port, pm.protocol, "dns")
                    else:
                        port_key = pm.host_port

                    assert (
                        port_key not in used_ports
                    ), f"Duplicate host port {pm.host_port} in environment {env_name}"
                    used_ports.add(port_key)

    def test_container_port_consistency(self):
        """Test container ports consistent across environments for same services."""
        services = ["apache", "mail", "dns"]

        for service in services:
            # Get container ports from development environment as reference
            dev_container_ports = {
                pm.container_port
                for pm in ENVIRONMENT_PORT_MAPPINGS["development"][service]
            }

            # Check all other environments have same container ports
            for env_name, env_mappings in ENVIRONMENT_PORT_MAPPINGS.items():
                if env_name == "development":
                    continue

                env_container_ports = {
                    pm.container_port for pm in env_mappings[service]
                }
                assert dev_container_ports == env_container_ports, (
                    f"Container ports mismatch for {service} between "
                    f"development and {env_name}"
                )
