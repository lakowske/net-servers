"""Tests for dynamic port allocation system."""

from unittest.mock import MagicMock, patch

import pytest

from net_servers.config.containers import (
    DYNAMIC_PORT_RANGE,
    SERVICE_CONTAINER_PORTS,
    _find_available_port,
    _get_all_used_ports,
    _is_port_available,
    generate_environment_port_mappings,
)


class TestPortAvailability:
    """Test port availability checking."""

    def test_is_port_available_free_port(self):
        """Test that free ports are detected as available."""
        # Test a high port that should be free
        result = _is_port_available(59999)
        # Can't guarantee result due to system state, just test it doesn't crash
        assert isinstance(result, bool)

    @patch("net_servers.config.containers.socket.socket")
    def test_is_port_available_mock_free(self, mock_socket):
        """Test port availability with mocked free port."""
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        mock_sock.bind.return_value = None  # No exception = port is free

        result = _is_port_available(8888)
        assert result is True
        mock_sock.bind.assert_called_once_with(("localhost", 8888))

    @patch("net_servers.config.containers.socket.socket")
    def test_is_port_available_mock_occupied(self, mock_socket):
        """Test port availability with mocked occupied port."""
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        mock_sock.bind.side_effect = OSError("Port already in use")

        result = _is_port_available(8888)
        assert result is False


class TestFindAvailablePort:
    """Test finding available ports."""

    @patch("net_servers.config.containers._is_port_available")
    def test_find_available_port_success(self, mock_is_available):
        """Test successful port finding."""
        mock_is_available.return_value = True

        port = _find_available_port(8500, 8600)
        assert 8500 <= port <= 8600
        mock_is_available.assert_called_once()

    @patch("net_servers.config.containers._is_port_available")
    def test_find_available_port_default_range(self, mock_is_available):
        """Test port finding with default range."""
        mock_is_available.return_value = True

        port = _find_available_port()
        assert DYNAMIC_PORT_RANGE[0] <= port <= DYNAMIC_PORT_RANGE[1]

    @patch("net_servers.config.containers._is_port_available")
    def test_find_available_port_failure(self, mock_is_available):
        """Test port finding failure after max attempts."""
        mock_is_available.return_value = False

        with pytest.raises(RuntimeError, match="Could not find available port"):
            _find_available_port(8500, 8600)


class TestGetAllUsedPorts:
    """Test getting all used ports."""

    def test_get_all_used_ports_no_config(self):
        """Test getting used ports without environment config."""
        used_ports = _get_all_used_ports()
        assert isinstance(used_ports, set)
        assert len(used_ports) > 0  # Should have predefined ports

    def test_get_all_used_ports_with_config(self):
        """Test getting used ports with environment config."""
        mock_env = MagicMock()
        mock_env.port_mappings = {
            "apache": [
                {"host_port": 9999, "container_port": 80},
                {"host_port": 9998, "container_port": 443},
            ]
        }
        mock_config = MagicMock()
        mock_config.environments = [mock_env]

        used_ports = _get_all_used_ports(mock_config)
        assert 9999 in used_ports
        assert 9998 in used_ports

    def test_get_all_used_ports_empty_port_mappings(self):
        """Test with environment that has empty port mappings."""
        mock_env = MagicMock()
        mock_env.port_mappings = {}
        mock_config = MagicMock()
        mock_config.environments = [mock_env]

        used_ports = _get_all_used_ports(mock_config)
        assert isinstance(used_ports, set)


class TestGenerateEnvironmentPortMappings:
    """Test environment port mapping generation."""

    @patch("net_servers.config.containers._find_available_port")
    def test_generate_port_mappings_success(self, mock_find_port):
        """Test successful port mapping generation."""
        # Mock _find_available_port to return incrementing ports
        port_counter = 8500

        def mock_port_finder():
            nonlocal port_counter
            port_counter += 1
            return port_counter

        mock_find_port.side_effect = mock_port_finder

        mappings = generate_environment_port_mappings("test-env")

        # Verify structure
        assert isinstance(mappings, dict)
        assert "apache" in mappings
        assert "mail" in mappings
        assert "dns" in mappings

        # Verify apache mappings
        apache_mappings = mappings["apache"]
        assert len(apache_mappings) == 2  # HTTP and HTTPS
        assert apache_mappings[0]["container_port"] == 80
        assert apache_mappings[1]["container_port"] == 443

        # Verify mail mappings
        mail_mappings = mappings["mail"]
        assert len(mail_mappings) == 6  # All mail ports

        # Verify DNS mappings
        dns_mappings = mappings["dns"]
        assert len(dns_mappings) == 2  # UDP and TCP

    @patch("net_servers.config.containers._find_available_port")
    def test_generate_port_mappings_with_conflicts(self, mock_find_port):
        """Test port mapping generation with port conflicts."""
        # First few calls return conflicted ports, then successful ones
        call_count = 0

        def mock_port_finder():
            nonlocal call_count
            call_count += 1
            return 8500 + call_count

        mock_find_port.side_effect = mock_port_finder

        # Create mock config with conflicting ports
        mock_env = MagicMock()
        mock_env.port_mappings = {"apache": [{"host_port": 8501}]}
        mock_config = MagicMock()
        mock_config.environments = [mock_env]

        mappings = generate_environment_port_mappings("test-env", mock_config)
        assert isinstance(mappings, dict)

    @patch("net_servers.config.containers._find_available_port")
    def test_generate_port_mappings_allocation_failure(self, mock_find_port):
        """Test port mapping generation when allocation fails."""
        mock_find_port.return_value = 8501  # Always return same port

        # Create mock config where 8501 is already used
        mock_env = MagicMock()
        mock_env.port_mappings = {"apache": [{"host_port": 8501}]}
        mock_config = MagicMock()
        mock_config.environments = [mock_env]

        with pytest.raises(RuntimeError, match="Could not allocate unique port"):
            generate_environment_port_mappings("test-env", mock_config)


class TestServiceContainerPorts:
    """Test service container port definitions."""

    def test_service_container_ports_structure(self):
        """Test that SERVICE_CONTAINER_PORTS has correct structure."""
        assert "apache" in SERVICE_CONTAINER_PORTS
        assert "mail" in SERVICE_CONTAINER_PORTS
        assert "dns" in SERVICE_CONTAINER_PORTS

        # Check apache ports
        apache_ports = SERVICE_CONTAINER_PORTS["apache"]
        assert len(apache_ports) == 2
        assert any(p["container_port"] == 80 for p in apache_ports)
        assert any(p["container_port"] == 443 for p in apache_ports)

        # Check mail ports
        mail_ports = SERVICE_CONTAINER_PORTS["mail"]
        assert len(mail_ports) == 6
        expected_mail_ports = [25, 143, 110, 993, 995, 587]
        for expected_port in expected_mail_ports:
            assert any(p["container_port"] == expected_port for p in mail_ports)

        # Check DNS ports
        dns_ports = SERVICE_CONTAINER_PORTS["dns"]
        assert len(dns_ports) == 2
        assert any(
            p["container_port"] == 53 and p["protocol"] == "udp" for p in dns_ports
        )
        assert any(
            p["container_port"] == 53 and p["protocol"] == "tcp" for p in dns_ports
        )
