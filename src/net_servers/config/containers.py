"""Container configuration management."""

from typing import Dict

from net_servers.actions.container import ContainerConfig, PortMapping

from .manager import ConfigurationManager

# Production port mappings (standard ports)
PRODUCTION_PORT_MAPPINGS = {
    "apache": [
        PortMapping(host_port=80, container_port=80),
        PortMapping(host_port=443, container_port=443),
    ],
    "mail": [
        PortMapping(host_port=25, container_port=25),  # SMTP
        PortMapping(host_port=143, container_port=143),  # IMAP
        PortMapping(host_port=110, container_port=110),  # POP3
        PortMapping(host_port=993, container_port=993),  # IMAPS
        PortMapping(host_port=995, container_port=995),  # POP3S
        PortMapping(host_port=587, container_port=587),  # SMTP submission
    ],
    "dns": [
        PortMapping(host_port=53, container_port=53, protocol="udp"),
        PortMapping(host_port=53, container_port=53, protocol="tcp"),
    ],
}

# Testing port mappings (non-conflicting ports)
TESTING_PORT_MAPPINGS = {
    "apache": [
        PortMapping(host_port=8080, container_port=80),
        PortMapping(host_port=8443, container_port=443),
    ],
    "mail": [
        PortMapping(host_port=2525, container_port=25),  # SMTP
        PortMapping(
            host_port=1144, container_port=143
        ),  # IMAP (avoiding ProtonMail Bridge on 1143)
        PortMapping(host_port=1110, container_port=110),  # POP3
        PortMapping(host_port=9993, container_port=993),  # IMAPS
        PortMapping(host_port=9995, container_port=995),  # POP3S
        PortMapping(host_port=5870, container_port=587),  # SMTP submission
    ],
    "dns": [
        PortMapping(
            host_port=5354, container_port=53, protocol="udp"
        ),  # Avoiding mDNS on 5353
        PortMapping(host_port=5354, container_port=53, protocol="tcp"),
    ],
}

# Base container configurations
CONTAINER_CONFIGS: Dict[str, ContainerConfig] = {
    "apache": ContainerConfig(
        image_name="net-servers-apache",
        dockerfile="docker/apache/Dockerfile",
        port=8080,  # Primary port for backward compatibility
        container_name="net-servers-apache",
    ),
    "mail": ContainerConfig(
        image_name="net-servers-mail",
        dockerfile="docker/mail/Dockerfile",
        port=2525,  # Primary port for backward compatibility
        container_name="net-servers-mail",
    ),
    "dns": ContainerConfig(
        image_name="net-servers-dns",
        dockerfile="docker/dns/Dockerfile",
        port=5353,  # Primary port for backward compatibility
        container_name="net-servers-dns",
    ),
}


def get_container_config(
    name: str,
    development_mode: bool = True,
    use_config_manager: bool = True,
    production_mode: bool = False,
) -> ContainerConfig:
    """Get container configuration by name with enhanced configuration.

    Args:
        name: Container name (apache, mail, dns)
        development_mode: Enable development features (volumes, etc.)
        use_config_manager: Use configuration manager for enhanced config
        production_mode: Use production ports and naming (vs testing mode)
    """
    if name not in CONTAINER_CONFIGS:
        available = ", ".join(CONTAINER_CONFIGS.keys())
        raise ValueError(f"Unknown container config '{name}'. Available: {available}")

    # Return a copy to avoid mutating the original config
    original = CONTAINER_CONFIGS[name]

    # Determine port mappings and container name based on mode
    if production_mode:
        port_mappings = PRODUCTION_PORT_MAPPINGS[name].copy()
        container_name = original.container_name or ""
        primary_port = port_mappings[0].host_port if port_mappings else original.port
    else:
        port_mappings = TESTING_PORT_MAPPINGS[name].copy()
        base_name = original.container_name or ""
        container_name = f"{base_name}-testing"
        primary_port = port_mappings[0].host_port if port_mappings else original.port

    config = ContainerConfig(
        image_name=original.image_name,
        dockerfile=original.dockerfile,
        port=primary_port,
        container_name=container_name,
        port_mappings=port_mappings,
    )

    # Enhance with configuration management if enabled
    if use_config_manager:
        try:
            # Use a local data directory for testing if /data doesn't exist
            import os

            base_path = (
                "/data"
                if os.path.exists("/data")
                else os.path.expanduser("~/.net-servers")
            )
            config_manager = ConfigurationManager(base_path)
            config_manager.initialize_default_configs()
            config = config_manager.enhance_container_config(
                config, name, development_mode
            )
        except (ImportError, PermissionError, OSError):
            # If config system not available or fails, return basic config
            pass

    return config


def list_container_configs() -> Dict[str, ContainerConfig]:
    """List all available container configurations."""
    return CONTAINER_CONFIGS.copy()
