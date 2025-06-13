"""Configuration schemas and validation for the net-servers project."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, Field, field_validator


class SystemConfig(BaseModel):
    """Global system configuration."""

    domain: str = Field(default="local.dev", description="Primary domain")
    admin_email: str = Field(
        default="admin@local.dev", description="Administrator email"
    )
    timezone: str = Field(default="UTC", description="System timezone")


class NetworkConfig(BaseModel):
    """Network configuration."""

    internal: str = Field(default="172.20.0.0/16", description="Internal network CIDR")


class SecurityConfig(BaseModel):
    """Security configuration."""

    tls_enabled: bool = Field(default=True, description="Enable TLS/SSL")
    cert_path: str = Field(
        default="/data/state/certificates", description="Certificate storage path"
    )


class GlobalConfig(BaseModel):
    """Global configuration schema."""

    system: SystemConfig = Field(default_factory=SystemConfig)
    networks: NetworkConfig = Field(default_factory=NetworkConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


class UserConfig(BaseModel):
    """User configuration schema."""

    username: str = Field(..., description="Username")
    email: str = Field(..., description="User email address")
    domains: List[str] = Field(
        default_factory=list, description="Domains user can access"
    )
    roles: List[str] = Field(default_factory=lambda: ["user"], description="User roles")
    mailbox_quota: str = Field(default="500M", description="Mailbox quota")
    enabled: bool = Field(default=True, description="User account enabled")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation."""
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v


class UsersConfig(BaseModel):
    """Users configuration schema."""

    users: List[UserConfig] = Field(default_factory=list, description="List of users")


class DomainConfig(BaseModel):
    """Domain configuration schema."""

    name: str = Field(..., description="Domain name")
    enabled: bool = Field(default=True, description="Domain enabled")
    mx_records: List[str] = Field(default_factory=list, description="MX records")
    a_records: Dict[str, str] = Field(default_factory=dict, description="A records")
    cname_records: Dict[str, str] = Field(
        default_factory=dict, description="CNAME records"
    )
    txt_records: Dict[str, str] = Field(default_factory=dict, description="TXT records")
    srv_records: List[Dict[str, Any]] = Field(
        default_factory=list, description="SRV records"
    )


class DomainsConfig(BaseModel):
    """Domains configuration schema."""

    domains: List[DomainConfig] = Field(
        default_factory=list, description="List of domains"
    )


class MailServiceConfig(BaseModel):
    """Mail service specific configuration."""

    postfix_main_cf: Dict[str, str] = Field(
        default_factory=dict, description="Postfix main.cf overrides"
    )
    dovecot_conf: Dict[str, str] = Field(
        default_factory=dict, description="Dovecot config overrides"
    )
    virtual_domains: List[str] = Field(
        default_factory=list, description="Virtual domains"
    )
    relay_domains: List[str] = Field(default_factory=list, description="Relay domains")


class DnsServiceConfig(BaseModel):
    """DNS service specific configuration."""

    forwarders: List[str] = Field(
        default_factory=lambda: ["8.8.8.8", "8.8.4.4"], description="DNS forwarders"
    )
    allow_query: List[str] = Field(
        default_factory=lambda: ["any"], description="Allow query ACL"
    )
    allow_recursion: List[str] = Field(
        default_factory=lambda: ["any"], description="Allow recursion ACL"
    )
    zone_file_path: str = Field(
        default="/etc/bind/zones", description="Zone files directory"
    )


class ApacheServiceConfig(BaseModel):
    """Apache service specific configuration."""

    document_root: str = Field(default="/var/www/html", description="Document root")
    server_admin: str = Field(
        default="admin@local.dev", description="Server admin email"
    )
    virtual_hosts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Virtual hosts"
    )
    modules: List[str] = Field(
        default_factory=list, description="Apache modules to enable"
    )


class ServicesConfig(BaseModel):
    """Services configuration schema."""

    mail: MailServiceConfig = Field(default_factory=MailServiceConfig)
    dns: DnsServiceConfig = Field(default_factory=DnsServiceConfig)
    apache: ApacheServiceConfig = Field(default_factory=ApacheServiceConfig)


@dataclass
class ConfigurationPaths:
    """Standard configuration paths."""

    base_path: Path = field(default_factory=lambda: Path("/data"))

    def __post_init__(self) -> None:
        """Set up all paths relative to base_path."""
        # Always set paths relative to base_path
        self.config_path = self.base_path / "config"
        self.state_path = self.base_path / "state"
        self.logs_path = self.base_path / "logs"
        self.code_path = self.base_path / "code"

    def ensure_directories(self) -> None:
        """Create directory structure if it doesn't exist."""
        for path in [self.config_path, self.state_path, self.logs_path, self.code_path]:
            path.mkdir(parents=True, exist_ok=True)

        # Create service-specific directories
        for service in ["mail", "dns", "apache"]:
            (self.state_path / service).mkdir(exist_ok=True)
            (self.logs_path / service).mkdir(exist_ok=True)

        # Create config subdirectories
        (self.config_path / "services").mkdir(exist_ok=True)
        (self.state_path / "mailboxes").mkdir(exist_ok=True)
        (self.state_path / "dns-zones").mkdir(exist_ok=True)
        (self.state_path / "certificates").mkdir(exist_ok=True)


def load_yaml_config(file_path: Path, schema_class: type) -> Any:
    """Load and validate YAML configuration file."""
    if not file_path.exists():
        # Return default instance if file doesn't exist
        return schema_class()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return schema_class(**data)
    except Exception as e:
        raise ValueError(f"Failed to load config from {file_path}: {e}")


def save_yaml_config(config: BaseModel, file_path: Path) -> None:
    """Save configuration to YAML file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)


def get_default_volumes(base_path: str = "/data") -> List[tuple]:
    """Get default volume mounts for development and production."""
    paths = ConfigurationPaths(base_path=Path(base_path))

    return [
        # Configuration volume (read-write for dynamic updates)
        (str(paths.config_path), "/data/config", False),
        # State volume (read-write for persistent data)
        (str(paths.state_path), "/data/state", False),
        # Logs volume (read-write for log files)
        (str(paths.logs_path), "/data/logs", False),
        # Code volume (read-only in production, read-write in development)
        (str(paths.code_path), "/data/code", False),  # Set to True for production
    ]
