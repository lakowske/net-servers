"""Container configuration management."""

import random
import socket
from typing import Any, Dict, List, Optional

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
    "default": {
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

# Port allocation range for dynamic environments (avoid system and well-known ports)
DYNAMIC_PORT_RANGE = (8500, 9999)

# Service container port templates for dynamic allocation
SERVICE_CONTAINER_PORTS = {
    "apache": [
        {"container_port": 80, "protocol": "tcp"},
        {"container_port": 443, "protocol": "tcp"},
    ],
    "mail": [
        {"container_port": 25, "protocol": "tcp"},  # SMTP
        {"container_port": 143, "protocol": "tcp"},  # IMAP
        {"container_port": 110, "protocol": "tcp"},  # POP3
        {"container_port": 993, "protocol": "tcp"},  # IMAPS
        {"container_port": 995, "protocol": "tcp"},  # POP3S
        {"container_port": 587, "protocol": "tcp"},  # SMTP submission
    ],
    "dns": [
        {"container_port": 53, "protocol": "udp"},
        {"container_port": 53, "protocol": "tcp"},
    ],
}


def _is_port_available(port: int) -> bool:
    """Check if a port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("localhost", port))
            return True
        except OSError:
            return False


def _find_available_port(
    start_range: Optional[int] = None, end_range: Optional[int] = None
) -> int:
    """Find a random available port in the specified range."""
    start_range = start_range or DYNAMIC_PORT_RANGE[0]
    end_range = end_range or DYNAMIC_PORT_RANGE[1]

    max_attempts = 100
    for _ in range(max_attempts):
        port = random.randint(start_range, end_range)  # nosec B311
        if _is_port_available(port):
            return port

    raise RuntimeError(
        f"Could not find available port in range {start_range}-{end_range}"
    )


def _get_all_used_ports(environments_config: Optional[Any] = None) -> set:
    """Get all ports currently used by environments."""
    used_ports = set()

    # Add predefined environment ports
    for env_name, services in ENVIRONMENT_PORT_MAPPINGS.items():
        for service_name, port_mappings in services.items():
            for pm in port_mappings:
                used_ports.add(pm.host_port)

    # Add dynamic environment ports if config provided
    if environments_config:
        for env in environments_config.environments:
            if hasattr(env, "port_mappings") and env.port_mappings:
                for service_name, port_configs in env.port_mappings.items():
                    for port_config in port_configs:
                        if "host_port" in port_config:
                            used_ports.add(port_config["host_port"])

    return used_ports


def generate_environment_port_mappings(
    environment_name: str, environments_config: Optional[Any] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Generate random port mappings for a new environment.

    Args:
        environment_name: Name of the environment
        environments_config: Existing environments config to avoid conflicts

    Returns:
        Dict mapping service names to port configuration lists
    """
    used_ports = _get_all_used_ports(environments_config)
    port_mappings = {}

    for service_name, container_ports in SERVICE_CONTAINER_PORTS.items():
        service_mappings = []

        for port_spec in container_ports:
            # Find available port avoiding conflicts
            max_attempts = 100
            for _ in range(max_attempts):
                host_port = _find_available_port()
                if host_port not in used_ports:
                    break
            else:
                raise RuntimeError(f"Could not allocate unique port for {service_name}")

            used_ports.add(host_port)
            service_mappings.append(
                {
                    "host_port": host_port,
                    "container_port": port_spec["container_port"],
                    "protocol": port_spec.get("protocol", "tcp"),
                }
            )

        port_mappings[service_name] = service_mappings

    return port_mappings


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
            # Use environment-aware configuration (no fallbacks)
            # Import here to avoid circular imports
            from net_servers.cli_environments import _get_config_manager

            config_manager = _get_config_manager()
            current_env = config_manager.get_current_environment()
            environment_name = current_env.name
        except Exception:
            # Fall back to default environment when config manager unavailable
            # This ensures CLI commands work even without environments.yaml
            use_config_manager = False
            environment_name = "default"
    elif environment_name is None:
        # When not using config manager, default to "default" environment
        environment_name = "default"

    # Determine port mappings and container name based on environment
    base_name = original.container_name or ""
    container_name = f"{base_name}-{environment_name}"

    # Use environment-specific ports to avoid conflicts between environments
    port_mappings = []

    # First, try to get port mappings from environment configuration
    if use_config_manager:
        try:
            from net_servers.cli_environments import _get_config_manager

            config_manager = _get_config_manager()
            current_env = config_manager.get_current_environment()

            # Check if environment has stored port mappings
            if (
                hasattr(current_env, "port_mappings")
                and current_env.port_mappings
                and name in current_env.port_mappings
            ):
                # Convert stored port configs to PortMapping objects
                for port_config in current_env.port_mappings[name]:
                    port_mappings.append(
                        PortMapping(
                            host_port=port_config["host_port"],
                            container_port=port_config["container_port"],
                            protocol=port_config.get("protocol", "tcp"),
                        )
                    )
        except Exception:  # nosec B110
            # Fall through to predefined mappings if config fails
            pass

    # Fallback to predefined environment mappings if no stored mappings found
    if not port_mappings:
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
            import os

            # Use a local data directory for testing if /data doesn't exist
            base_path = (
                "/data"
                if os.path.exists("/data")
                else os.path.expanduser("~/.net-servers")
            )

            # Get environments config path for ConfigurationManager
            from net_servers.cli_environments import _get_environments_config_path

            env_config_path = _get_environments_config_path()

            config_manager = ConfigurationManager(
                base_path, environments_config_path=env_config_path
            )

            # Get current environment and use its base path for container volumes
            current_env = config_manager.get_current_environment()
            env_config_manager = ConfigurationManager(
                current_env.base_path, environments_config_path=env_config_path
            )
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
