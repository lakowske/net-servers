"""Tests for the dynamic port allocation system."""

import pytest

from .port_manager import IntegrationPortManager, get_port_manager


class TestIntegrationPortManager:
    """Test the IntegrationPortManager class."""

    def test_port_availability_check(self):
        """Test port availability checking."""
        manager = IntegrationPortManager()

        # Port 0 should always be available (kernel assigns)
        assert manager.is_port_available(0)

        # Port 1 should typically be unavailable (requires root)
        assert not manager.is_port_available(1)

    def test_find_available_port(self):
        """Test finding available ports in range."""
        manager = IntegrationPortManager()

        # Should find a port in the 5000-5010 range
        port = manager.find_available_port(5000, 5010)
        assert port is not None
        assert 5000 <= port <= 5010

    def test_service_port_allocation(self):
        """Test allocating ports for known services."""
        manager = IntegrationPortManager()

        # Test Apache service
        apache_ports = manager.allocate_service_ports("apache")
        assert 80 in apache_ports  # Apache container port
        assert 5080 <= apache_ports[80] <= 5099  # Host port in range

        # Test Mail service
        mail_ports = manager.allocate_service_ports("mail")
        expected_mail_ports = [25, 143, 110, 587, 993, 995]
        for container_port in expected_mail_ports:
            assert container_port in mail_ports
            assert 5100 <= mail_ports[container_port] <= 5199

        # Test DNS service
        dns_ports = manager.allocate_service_ports("dns")
        assert 53 in dns_ports  # DNS container port
        assert 5300 <= dns_ports[53] <= 5399  # Host port in range

    def test_port_mapping_string_generation(self):
        """Test generating port mapping strings for containers."""
        manager = IntegrationPortManager()

        # Test Apache
        apache_mapping = manager.get_port_mapping_string("apache")
        assert ":" in apache_mapping
        assert apache_mapping.endswith(":80")  # Container port

        # Test Mail (should have multiple mappings)
        mail_mapping = manager.get_port_mapping_string("mail")
        assert "," in mail_mapping  # Multiple port mappings
        assert ":25" in mail_mapping
        assert ":143" in mail_mapping
        assert ":110" in mail_mapping

    def test_duplicate_allocation_consistency(self):
        """Test that repeated allocations return the same ports."""
        manager = IntegrationPortManager()

        # Allocate Apache ports twice
        ports1 = manager.allocate_service_ports("apache")
        ports2 = manager.allocate_service_ports("apache")

        assert ports1 == ports2  # Should be identical

    def test_port_conflict_prevention(self):
        """Test that different services get different ports."""
        manager = IntegrationPortManager()

        # Allocate ports for all services
        apache_ports = manager.allocate_service_ports("apache")
        mail_ports = manager.allocate_service_ports("mail")
        dns_ports = manager.allocate_service_ports("dns")

        # Get all allocated host ports
        all_host_ports = set()
        all_host_ports.update(apache_ports.values())
        all_host_ports.update(mail_ports.values())
        all_host_ports.update(dns_ports.values())

        # Should have no duplicate host ports
        total_ports = len(apache_ports) + len(mail_ports) + len(dns_ports)
        assert len(all_host_ports) == total_ports

    def test_host_port_lookup(self):
        """Test looking up host ports for specific container ports."""
        manager = IntegrationPortManager()

        # Allocate mail service ports
        manager.allocate_service_ports("mail")

        # Look up specific ports
        smtp_port = manager.get_host_port("mail", 25)
        imap_port = manager.get_host_port("mail", 143)
        pop3_port = manager.get_host_port("mail", 110)

        assert 5100 <= smtp_port <= 5199
        assert 5100 <= imap_port <= 5199
        assert 5100 <= pop3_port <= 5199

        # All should be different
        assert len({smtp_port, imap_port, pop3_port}) == 3

    def test_unknown_service_error(self):
        """Test error handling for unknown services."""
        manager = IntegrationPortManager()

        with pytest.raises(ValueError, match="Unknown service"):
            manager.allocate_service_ports("unknown_service")

    def test_missing_port_error(self):
        """Test error handling for missing container ports."""
        manager = IntegrationPortManager()

        # Allocate apache service
        manager.allocate_service_ports("apache")

        # Try to look up a port that Apache doesn't have
        with pytest.raises(KeyError):
            manager.get_host_port("apache", 25)  # Apache doesn't use port 25

    def test_port_release(self):
        """Test releasing allocated ports."""
        manager = IntegrationPortManager()

        # Allocate ports
        original_ports = manager.allocate_service_ports("apache")

        # Release them
        manager.release_service_ports("apache")

        # Allocate again - should get potentially different ports
        new_ports = manager.allocate_service_ports("apache")

        # Should have the same structure (same container ports)
        assert set(original_ports.keys()) == set(new_ports.keys())

    def test_service_info(self):
        """Test getting comprehensive service information."""
        manager = IntegrationPortManager()

        info = manager.get_service_info("mail")

        assert info["service"] == "mail"
        assert "port_mappings" in info
        assert "mapping_string" in info
        assert "connection_info" in info

        # Check connection info format
        connection_info = info["connection_info"]
        assert "port_25" in connection_info
        assert connection_info["port_25"]["container_port"] == 25
        assert "host_port" in connection_info["port_25"]
        assert "connection_url" in connection_info["port_25"]


class TestGlobalPortManager:
    """Test the global port manager instance."""

    def test_global_instance_consistency(self):
        """Test that get_port_manager returns consistent instance."""
        manager1 = get_port_manager()
        manager2 = get_port_manager()

        assert manager1 is manager2  # Should be same instance

    def test_convenience_functions(self):
        """Test convenience functions work with global instance."""
        from .port_manager import (
            allocate_service_ports,
            get_host_port,
            get_port_mapping_string,
        )

        # Test convenience functions
        ports = allocate_service_ports("dns")
        mapping_string = get_port_mapping_string("dns")
        host_port = get_host_port("dns", 53)

        assert 53 in ports
        assert ":" in mapping_string
        assert 5300 <= host_port <= 5399

    def test_port_range_boundaries(self):
        """Test that port allocation respects defined ranges."""
        manager = IntegrationPortManager()

        # Clear any existing allocations
        manager.release_all_ports()

        # Test each service's port range
        apache_ports = manager.allocate_service_ports("apache")
        for host_port in apache_ports.values():
            assert 5080 <= host_port <= 5099

        mail_ports = manager.allocate_service_ports("mail")
        for host_port in mail_ports.values():
            assert 5100 <= host_port <= 5199

        dns_ports = manager.allocate_service_ports("dns")
        for host_port in dns_ports.values():
            assert 5300 <= host_port <= 5399
