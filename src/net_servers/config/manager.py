"""Configuration management for the net-servers project."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from ..actions.container import ContainerConfig, VolumeMount
from .certificates import CertificateConfig, CertificateManager, CertificateMode
from .schemas import (
    ConfigurationPaths,
    DomainConfig,
    DomainsConfig,
    GlobalConfig,
    ServicesConfig,
    UserConfig,
    UsersConfig,
    get_default_volumes,
    load_yaml_config,
    save_yaml_config,
)


class ConfigurationManager:
    """Manages configuration loading, validation, and persistence."""

    def __init__(self, base_path: str = "/data"):
        """Initialize configuration manager."""
        self.logger = logging.getLogger(__name__)
        self.paths = ConfigurationPaths(base_path=Path(base_path))

        # Ensure directory structure exists
        self.paths.ensure_directories()

        # Certificate manager for SSL support
        self.cert_manager = CertificateManager(
            str(self.paths.state_path / "certificates")
        )

        # Configuration cache
        self._global_config: Optional[GlobalConfig] = None
        self._users_config: Optional[UsersConfig] = None
        self._domains_config: Optional[DomainsConfig] = None
        self._services_config: Optional[ServicesConfig] = None

    @property
    def global_config(self) -> GlobalConfig:
        """Get global configuration."""
        if self._global_config is None:
            self._global_config = load_yaml_config(
                self.paths.config_path / "global.yaml", GlobalConfig
            )
        return self._global_config

    @property
    def users_config(self) -> UsersConfig:
        """Get users configuration."""
        if self._users_config is None:
            self._users_config = load_yaml_config(
                self.paths.config_path / "users.yaml", UsersConfig
            )
        return self._users_config

    @property
    def domains_config(self) -> DomainsConfig:
        """Get domains configuration."""
        if self._domains_config is None:
            self._domains_config = load_yaml_config(
                self.paths.config_path / "domains.yaml", DomainsConfig
            )
        return self._domains_config

    @property
    def services_config(self) -> ServicesConfig:
        """Get services configuration."""
        if self._services_config is None:
            self._services_config = load_yaml_config(
                self.paths.config_path / "services" / "services.yaml", ServicesConfig
            )
        return self._services_config

    def reload_config(self) -> None:
        """Reload all configuration from disk."""
        self.logger.info("Reloading configuration from disk")
        self._global_config = None
        self._users_config = None
        self._domains_config = None
        self._services_config = None

    def save_global_config(self, config: GlobalConfig) -> None:
        """Save global configuration to disk."""
        save_yaml_config(config, self.paths.config_path / "global.yaml")
        self._global_config = config

    def save_users_config(self, config: UsersConfig) -> None:
        """Save users configuration to disk."""
        save_yaml_config(config, self.paths.config_path / "users.yaml")
        self._users_config = config

    def save_domains_config(self, config: DomainsConfig) -> None:
        """Save domains configuration to disk."""
        save_yaml_config(config, self.paths.config_path / "domains.yaml")
        self._domains_config = config

    def save_services_config(self, config: ServicesConfig) -> None:
        """Save services configuration to disk."""
        save_yaml_config(config, self.paths.config_path / "services" / "services.yaml")
        self._services_config = config

    def get_container_volumes(self, development_mode: bool = True) -> List[VolumeMount]:
        """Get volume mounts for containers."""
        volumes = []

        for host_path, container_path, read_only in get_default_volumes(
            str(self.paths.base_path)
        ):
            # In development mode, make code volume writable
            if container_path == "/data/code" and development_mode:
                read_only = False

            volumes.append(
                VolumeMount(
                    host_path=host_path,
                    container_path=container_path,
                    read_only=read_only,
                )
            )

        return volumes

    def get_container_environment(self, service_name: str) -> Dict[str, str]:
        """Get environment variables for a specific service."""
        env = {
            "SERVICE_NAME": service_name,
            "CONFIG_PATH": "/data/config",
            "STATE_PATH": "/data/state",
            "LOGS_PATH": "/data/logs",
            "DOMAIN": self.global_config.system.domain,
            "ADMIN_EMAIL": self.global_config.system.admin_email,
            "TZ": self.global_config.system.timezone,
        }

        # Add service-specific environment variables
        if service_name == "mail":
            mail_config = self.services_config.mail
            env.update(
                {
                    "VIRTUAL_DOMAINS": ",".join(mail_config.virtual_domains),
                    "RELAY_DOMAINS": ",".join(mail_config.relay_domains),
                    "MAIL_TLS_ENABLED": "true" if mail_config.tls_enabled else "false",
                    "MAIL_REQUIRE_TLS": "true" if mail_config.require_tls else "false",
                    "MAIL_SSL_CERT_FILE": mail_config.ssl_cert_file,
                    "MAIL_SSL_KEY_FILE": mail_config.ssl_key_file,
                    "MAIL_SSL_CHAIN_FILE": mail_config.ssl_chain_file,
                }
            )
        elif service_name == "dns":
            dns_config = self.services_config.dns
            env.update(
                {
                    "DNS_FORWARDERS": ",".join(dns_config.forwarders),
                    "ZONE_FILE_PATH": dns_config.zone_file_path,
                }
            )
        elif service_name == "apache":
            apache_config = self.services_config.apache
            env.update(
                {
                    "DOCUMENT_ROOT": apache_config.document_root,
                    "SERVER_ADMIN": apache_config.server_admin,
                    "APACHE_SERVER_NAME": self.global_config.system.domain,
                    "APACHE_SERVER_ADMIN": apache_config.server_admin,
                    "APACHE_DOCUMENT_ROOT": apache_config.document_root,
                    "SSL_ENABLED": "true" if apache_config.ssl_enabled else "false",
                    "SSL_CERT_FILE": apache_config.ssl_cert_file,
                    "SSL_KEY_FILE": apache_config.ssl_key_file,
                    "SSL_CHAIN_FILE": apache_config.ssl_chain_file,
                }
            )

        return env

    def enhance_container_config(
        self, config: ContainerConfig, service_name: str, development_mode: bool = True
    ) -> ContainerConfig:
        """Enhance container configuration with volumes and environment."""
        # Add volumes
        config.volumes.extend(self.get_container_volumes(development_mode))

        # Add environment variables
        env_vars = self.get_container_environment(service_name)

        # For testing containers, enable SSL and ensure certificates exist
        if "testing" in config.container_name:
            self.logger.info(f"Enabling SSL for testing container: {service_name}")

            # Ensure SSL certificates are available
            cert_available = self.ensure_ssl_certificates()

            if cert_available:
                domain = self.global_config.system.domain
                if service_name == "apache":
                    cert_path = f"/data/state/certificates/{domain}/cert.pem"
                    key_path = f"/data/state/certificates/{domain}/privkey.pem"
                    chain_path = f"/data/state/certificates/{domain}/fullchain.pem"
                    env_vars.update(
                        {
                            "SSL_ENABLED": "true",
                            "SSL_CERT_FILE": cert_path,
                            "SSL_KEY_FILE": key_path,
                            "SSL_CHAIN_FILE": chain_path,
                        }
                    )
                elif service_name == "mail":
                    cert_path = f"/data/state/certificates/{domain}/cert.pem"
                    key_path = f"/data/state/certificates/{domain}/privkey.pem"
                    chain_path = f"/data/state/certificates/{domain}/fullchain.pem"
                    env_vars.update(
                        {
                            "MAIL_TLS_ENABLED": "true",
                            "MAIL_REQUIRE_TLS": "false",  # Allow both for testing
                            "MAIL_SSL_CERT_FILE": cert_path,
                            "MAIL_SSL_KEY_FILE": key_path,
                            "MAIL_SSL_CHAIN_FILE": chain_path,
                        }
                    )
            else:
                msg = f"SSL certificates not available for {service_name}"
                msg += ", running without SSL"
                self.logger.warning(msg)

        config.environment.update(env_vars)

        # Add service-specific configuration
        if service_name == "mail":
            config.state_paths.extend(
                [
                    "/data/state/mailboxes",
                    "/data/state/mail",
                ]
            )
        elif service_name == "dns":
            config.state_paths.extend(
                [
                    "/data/state/dns-zones",
                    "/data/state/dns",
                ]
            )
        elif service_name == "apache":
            config.state_paths.extend(
                [
                    "/data/state/certificates",
                    "/data/state/apache",
                ]
            )

        return config

    def initialize_default_configs(self) -> None:
        """Initialize default configuration files if they don't exist."""
        self.logger.info("Initializing default configuration files")

        # Create default global config
        if not (self.paths.config_path / "global.yaml").exists():
            default_global = GlobalConfig()
            self.save_global_config(default_global)

        # Create default users config with admin user
        if not (self.paths.config_path / "users.yaml").exists():
            default_users = UsersConfig(
                users=[
                    UserConfig(
                        username="admin",
                        email=f"admin@{self.global_config.system.domain}",
                        domains=[self.global_config.system.domain],
                        roles=["admin"],
                        mailbox_quota="1G",
                    )
                ]
            )
            self.save_users_config(default_users)

        # Create default domains config
        if not (self.paths.config_path / "domains.yaml").exists():
            default_domains = DomainsConfig(
                domains=[
                    DomainConfig(
                        name=self.global_config.system.domain,
                        mx_records=[f"mail.{self.global_config.system.domain}"],
                        a_records={
                            "mail": "172.20.0.10",
                            "www": "172.20.0.20",
                            "dns": "172.20.0.30",
                        },
                    )
                ]
            )
            self.save_domains_config(default_domains)

        # Create default services config
        if not (self.paths.config_path / "services" / "services.yaml").exists():
            default_services = ServicesConfig()
            default_services.mail.virtual_domains = [self.global_config.system.domain]
            self.save_services_config(default_services)

    def validate_configuration(self) -> List[str]:
        """Validate all configuration and return list of errors."""
        errors = []

        try:
            # Validate that all referenced domains exist
            domain_names = {domain.name for domain in self.domains_config.domains}

            # Check user domains
            for user in self.users_config.users:
                for domain in user.domains:
                    if domain not in domain_names:
                        errors.append(
                            f"User {user.username} references unknown domain: {domain}"
                        )

            # Check service domains
            for domain in self.services_config.mail.virtual_domains:
                if domain not in domain_names:
                    errors.append(
                        f"Mail service references unknown virtual domain: {domain}"
                    )

            # Validate email addresses
            for user in self.users_config.users:
                if "@" not in user.email:
                    errors.append(
                        f"Invalid email for user {user.username}: {user.email}"
                    )

        except (OSError, ValueError, KeyError) as e:
            errors.append(f"Configuration validation error: {e}")

        return errors

    def ensure_ssl_certificates(self, domain: Optional[str] = None) -> bool:
        """Ensure SSL certificates exist for domain, creating self-signed if needed.

        Args:
            domain: Domain to create certificates for. Uses global config if None.

        Returns:
            True if certificates are available, False otherwise.
        """
        if domain is None:
            domain = self.global_config.system.domain

        # Check if certificates already exist
        cert_dir = self.paths.state_path / "certificates" / domain
        cert_files = ["cert.pem", "privkey.pem", "fullchain.pem"]

        if all((cert_dir / f).exists() for f in cert_files):
            self.logger.debug(f"SSL certificates already exist for {domain}")
            return True

        # Create self-signed certificates for testing
        self.logger.info(f"Creating self-signed SSL certificates for {domain}")

        try:
            config = CertificateConfig(
                domain=domain,
                email=self.global_config.system.admin_email,
                mode=CertificateMode.SELF_SIGNED,
                san_domains=[f"mail.{domain}", f"www.{domain}", f"dns.{domain}"],
                cert_path=str(cert_dir / "cert.pem"),
                key_path=str(cert_dir / "privkey.pem"),
                fullchain_path=str(cert_dir / "fullchain.pem"),
            )

            return self.cert_manager.provision_certificate(config)

        except Exception as e:
            self.logger.error(f"Failed to create SSL certificates for {domain}: {e}")
            return False
