"""Dynamic port allocation for integration tests.

This module provides utilities to automatically allocate available ports
in the 5XXX range to avoid conflicts with system services and other containers.
"""

import socket
from typing import Dict, Optional, Set


class IntegrationPortManager:
    """Manages dynamic port allocation for integration tests."""

    # Port ranges for different services
    PORT_RANGES = {
        "apache": (5080, 5099),  # HTTP services
        "mail": (5100, 5199),  # Mail services (SMTP, IMAP, POP3)
        "dns": (5300, 5399),  # DNS services
        "general": (5400, 5499),  # General purpose
    }

    # Standard service ports that need mapping
    SERVICE_PORTS = {
        "apache": [80],
        "mail": [25, 143, 110, 587, 993, 995],
        "dns": [53],
    }

    def __init__(self):
        """Initialize port manager."""
        self._allocated_ports: Set[int] = set()
        self._service_mappings: Dict[str, Dict[int, int]] = {}

    def is_port_available(self, port: int) -> bool:
        """Check if a port is available for binding.

        Args:
            port: Port number to check

        Returns:
            True if port is available, False otherwise
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

    def find_available_port(self, start_port: int, end_port: int) -> Optional[int]:
        """Find the first available port in the given range.

        Args:
            start_port: Start of port range (inclusive)
            end_port: End of port range (inclusive)

        Returns:
            First available port number, or None if none found
        """
        for port in range(start_port, end_port + 1):
            if port not in self._allocated_ports and self.is_port_available(port):
                return port
        return None

    def allocate_service_ports(self, service_name: str) -> Dict[int, int]:
        """Allocate ports for a service, mapping container ports to host ports.

        Args:
            service_name: Name of the service (apache, mail, dns)

        Returns:
            Dictionary mapping container_port -> host_port

        Raises:
            ValueError: If service is unknown or no ports available
        """
        if service_name not in self.SERVICE_PORTS:
            raise ValueError(f"Unknown service: {service_name}")

        if service_name in self._service_mappings:
            return self._service_mappings[service_name]

        container_ports = self.SERVICE_PORTS[service_name]
        start_port, end_port = self.PORT_RANGES[service_name]

        mappings = {}
        for container_port in container_ports:
            host_port = self.find_available_port(start_port, end_port)
            if host_port is None:
                # Clean up any allocated ports if we can't allocate all
                for allocated_host_port in mappings.values():
                    self._allocated_ports.discard(allocated_host_port)
                raise ValueError(
                    f"No available ports in range {start_port}-{end_port} "
                    f"for service {service_name}"
                )

            mappings[container_port] = host_port
            self._allocated_ports.add(host_port)

        self._service_mappings[service_name] = mappings
        return mappings

    def get_port_mapping_string(self, service_name: str) -> str:
        """Get port mapping string for container runtime.

        Args:
            service_name: Name of the service

        Returns:
            Port mapping string in format "host1:container1,host2:container2,..."
        """
        mappings = self.allocate_service_ports(service_name)

        # Sort by container port for consistent ordering
        sorted_mappings = sorted(mappings.items())

        mapping_parts = []
        for container_port, host_port in sorted_mappings:
            mapping_parts.append(f"{host_port}" + ":" + str(container_port))

        return ",".join(mapping_parts)

    def get_host_port(self, service_name: str, container_port: int) -> int:
        """Get the host port for a specific container port.

        Args:
            service_name: Name of the service
            container_port: Container port number

        Returns:
            Host port number

        Raises:
            KeyError: If service or port not found
        """
        if service_name not in self._service_mappings:
            self.allocate_service_ports(service_name)

        mappings = self._service_mappings[service_name]
        if container_port not in mappings:
            raise KeyError(
                f"Container port {container_port} not found for service {service_name}"
            )

        return mappings[container_port]

    def release_service_ports(self, service_name: str) -> None:
        """Release all allocated ports for a service.

        Args:
            service_name: Name of the service
        """
        if service_name in self._service_mappings:
            mappings = self._service_mappings[service_name]
            for host_port in mappings.values():
                self._allocated_ports.discard(host_port)
            del self._service_mappings[service_name]

    def release_all_ports(self) -> None:
        """Release all allocated ports."""
        self._allocated_ports.clear()
        self._service_mappings.clear()

    def get_service_info(self, service_name: str) -> Dict[str, any]:
        """Get comprehensive information about a service's port allocation.

        Args:
            service_name: Name of the service

        Returns:
            Dictionary with port mappings and connection info
        """
        mappings = self.allocate_service_ports(service_name)

        return {
            "service": service_name,
            "port_mappings": mappings,
            "mapping_string": self.get_port_mapping_string(service_name),
            "connection_info": {
                f"port_{container_port}": {
                    "host_port": host_port,
                    "container_port": container_port,
                    "connection_url": "localhost:" + str(host_port),
                }
                for container_port, host_port in mappings.items()
            },
        }


# Global instance for shared use across test modules
_port_manager = IntegrationPortManager()


def get_port_manager() -> IntegrationPortManager:
    """Get the global port manager instance.

    Returns:
        Shared IntegrationPortManager instance
    """
    return _port_manager


def allocate_service_ports(service_name: str) -> Dict[int, int]:
    """Convenience function to allocate ports for a service.

    Args:
        service_name: Name of the service (apache, mail, dns)

    Returns:
        Dictionary mapping container_port -> host_port
    """
    return get_port_manager().allocate_service_ports(service_name)


def get_port_mapping_string(service_name: str) -> str:
    """Convenience function to get port mapping string.

    Args:
        service_name: Name of the service

    Returns:
        Port mapping string for container runtime
    """
    return get_port_manager().get_port_mapping_string(service_name)


def get_host_port(service_name: str, container_port: int) -> int:
    """Convenience function to get host port for container port.

    Args:
        service_name: Name of the service
        container_port: Container port number

    Returns:
        Host port number
    """
    return get_port_manager().get_host_port(service_name, container_port)
