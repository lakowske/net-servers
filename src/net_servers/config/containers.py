"""Container configuration management."""

from typing import Dict

from net_servers.actions.container import ContainerConfig

from .manager import ConfigurationManager

# Predefined container configurations
CONTAINER_CONFIGS: Dict[str, ContainerConfig] = {
    "apache": ContainerConfig(
        image_name="net-servers-apache",
        dockerfile="docker/apache/Dockerfile",
        port=8080,
        container_name="net-servers-apache",
    ),
    "mail": ContainerConfig(
        image_name="net-servers-mail",
        dockerfile="docker/mail/Dockerfile",
        port=25,
        container_name="net-servers-mail",
    ),
    "dns": ContainerConfig(
        image_name="net-servers-dns",
        dockerfile="docker/dns/Dockerfile",
        port=53,
        container_name="net-servers-dns",
    ),
}


def get_container_config(
    name: str, development_mode: bool = True, use_config_manager: bool = True
) -> ContainerConfig:
    """Get container configuration by name with enhanced configuration."""
    if name not in CONTAINER_CONFIGS:
        available = ", ".join(CONTAINER_CONFIGS.keys())
        raise ValueError(f"Unknown container config '{name}'. Available: {available}")

    # Return a copy to avoid mutating the original config
    original = CONTAINER_CONFIGS[name]
    config = ContainerConfig(
        image_name=original.image_name,
        dockerfile=original.dockerfile,
        port=original.port,
        container_name=original.container_name or "",
    )

    # Enhance with configuration management if enabled
    if use_config_manager:
        try:
            config_manager = ConfigurationManager()
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
