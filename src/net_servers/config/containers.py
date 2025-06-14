"""Container configuration management."""

from typing import Dict, Optional

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

# Environment-specific port mappings (to avoid conflicts between environments)
ENVIRONMENT_PORT_MAPPINGS = {
    "development": {
        "apache": [
            PortMapping(host_port=8080, container_port=80),
            PortMapping(host_port=8443, container_port=443),
        ],
        "mail": [
            PortMapping(host_port=2525, container_port=25),  # SMTP
            PortMapping(host_port=1144, container_port=143),  # IMAP
            PortMapping(host_port=1110, container_port=110),  # POP3
            PortMapping(host_port=9993, container_port=993),  # IMAPS
            PortMapping(host_port=9995, container_port=995),  # POP3S
            PortMapping(host_port=5870, container_port=587),  # SMTP submission
        ],
        "dns": [
            PortMapping(host_port=5354, container_port=53, protocol="udp"),
            PortMapping(host_port=5354, container_port=53, protocol="tcp"),
        ],
    },
    "testing": {
        "apache": [
            PortMapping(host_port=8180, container_port=80),
            PortMapping(host_port=8543, container_port=443),
        ],
        "mail": [
            PortMapping(host_port=2625, container_port=25),  # SMTP
            PortMapping(host_port=1244, container_port=143),  # IMAP
            PortMapping(host_port=1210, container_port=110),  # POP3
            PortMapping(host_port=9893, container_port=993),  # IMAPS
            PortMapping(host_port=9895, container_port=995),  # POP3S
            PortMapping(host_port=5970, container_port=587),  # SMTP submission
        ],
        "dns": [
            PortMapping(host_port=5454, container_port=53, protocol="udp"),
            PortMapping(host_port=5454, container_port=53, protocol="tcp"),
        ],
    },
    "staging": {
        "apache": [
            PortMapping(host_port=8280, container_port=80),
            PortMapping(host_port=8643, container_port=443),
        ],
        "mail": [
            PortMapping(host_port=2725, container_port=25),  # SMTP
            PortMapping(host_port=1344, container_port=143),  # IMAP
            PortMapping(host_port=1310, container_port=110),  # POP3
            PortMapping(host_port=9793, container_port=993),  # IMAPS
            PortMapping(host_port=9795, container_port=995),  # POP3S
            PortMapping(host_port=5770, container_port=587),  # SMTP submission
        ],
        "dns": [
            PortMapping(host_port=5554, container_port=53, protocol="udp"),
            PortMapping(host_port=5554, container_port=53, protocol="tcp"),
        ],
    },
    "production": {
        "apache": [
            PortMapping(host_port=8380, container_port=80),
            PortMapping(host_port=8743, container_port=443),
        ],
        "mail": [
            PortMapping(host_port=2825, container_port=25),  # SMTP
            PortMapping(host_port=1444, container_port=143),  # IMAP
            PortMapping(host_port=1410, container_port=110),  # POP3
            PortMapping(host_port=9693, container_port=993),  # IMAPS
            PortMapping(host_port=9695, container_port=995),  # POP3S
            PortMapping(host_port=5670, container_port=587),  # SMTP submission
        ],
        "dns": [
            PortMapping(host_port=5654, container_port=53, protocol="udp"),
            PortMapping(host_port=5654, container_port=53, protocol="tcp"),
        ],
    },
}

# Legacy testing port mappings (for backward compatibility)
TESTING_PORT_MAPPINGS = ENVIRONMENT_PORT_MAPPINGS["development"]

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
    environment_name: Optional[str] = None,
) -> ContainerConfig:
    """Get container configuration by name with enhanced configuration.

    Args:
        name: Container name (apache, mail, dns)
        development_mode: Enable development features (volumes, etc.)
        use_config_manager: Use configuration manager for enhanced config
        environment_name: Environment name for container isolation (auto-detected)
    """
    if name not in CONTAINER_CONFIGS:
        available = ", ".join(CONTAINER_CONFIGS.keys())
        raise ValueError(f"Unknown container config '{name}'. Available: {available}")

    # Return a copy to avoid mutating the original config
    original = CONTAINER_CONFIGS[name]

    # Auto-detect environment if not provided and config manager is available
    if environment_name is None and use_config_manager:
        try:
            import os

            base_path = (
                "/data"
                if os.path.exists("/data")
                else os.path.expanduser("~/.net-servers")
            )
            config_manager = ConfigurationManager(base_path)
            current_env = config_manager.get_current_environment()
            environment_name = current_env.name
        except Exception:
            environment_name = "development"
    elif environment_name is None:
        environment_name = "development"

    # Determine port mappings and container name based on environment
    base_name = original.container_name or ""
    container_name = f"{base_name}-{environment_name}"

    # Use environment-specific ports to avoid conflicts between environments
    if environment_name in ENVIRONMENT_PORT_MAPPINGS:
        port_mappings = ENVIRONMENT_PORT_MAPPINGS[environment_name][name].copy()
    else:
        # Fallback to development ports for unknown environments
        port_mappings = ENVIRONMENT_PORT_MAPPINGS["development"][name].copy()

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

            # Get current environment and use its base path for container volumes
            current_env = config_manager.get_current_environment()
            env_config_manager = ConfigurationManager(current_env.base_path)
            env_config_manager.initialize_default_configs()

            config = env_config_manager.enhance_container_config(
                config, name, development_mode
            )
        except (ImportError, PermissionError, OSError):
            # If config system not available or fails, return basic config
            pass

    return config


def list_container_configs() -> Dict[str, ContainerConfig]:
    """List all available container configurations."""
    return CONTAINER_CONFIGS.copy()
