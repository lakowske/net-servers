"""Configuration synchronization system for YAML configs to services."""

import logging
import shutil
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from ..actions.container import ContainerManager
from .manager import ConfigurationManager
from .schemas import DomainConfig, UserConfig


class ServiceSynchronizer(ABC):
    """Base class for service configuration synchronizers."""

    def __init__(self, config_manager: ConfigurationManager):
        """Initialize synchronizer with configuration manager."""
        self.config_manager = config_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def sync_users(self, users: List[UserConfig]) -> bool:
        """Synchronize user configuration to service."""
        pass

    @abstractmethod
    def sync_domains(self, domains: List[DomainConfig]) -> bool:
        """Synchronize domain configuration to service."""
        pass

    @abstractmethod
    def validate_configuration(self) -> List[str]:
        """Validate current service configuration and return errors."""
        pass

    @abstractmethod
    def reload_service(self) -> bool:
        """Reload service to pick up configuration changes."""
        pass


class MailServiceSynchronizer(ServiceSynchronizer):
    """Synchronizes configuration changes to mail service (Postfix + Dovecot)."""

    def __init__(
        self,
        config_manager: ConfigurationManager,
        container_manager: Optional[ContainerManager] = None,
    ):
        """Initialize mail service synchronizer."""
        super().__init__(config_manager)
        self.container_manager = container_manager

    def sync_users(self, users: List[UserConfig]) -> bool:
        """Synchronize users to Postfix virtual_users and Dovecot users."""
        try:
            # Generate Postfix virtual users file
            virtual_users_content = self._generate_virtual_users(users)
            virtual_users_path = (
                self.config_manager.paths.state_path / "mail" / "virtual_users"
            )
            virtual_users_path.parent.mkdir(parents=True, exist_ok=True)

            with open(virtual_users_path, "w", encoding="utf-8") as f:
                f.write(virtual_users_content)

            # Generate Dovecot users file
            dovecot_users_content = self._generate_dovecot_users(users)
            dovecot_users_path = (
                self.config_manager.paths.state_path / "mail" / "dovecot_users"
            )

            with open(dovecot_users_path, "w", encoding="utf-8") as f:
                f.write(dovecot_users_content)

            # Create user mailboxes
            self._create_user_mailboxes(users)

            self.logger.info(f"Synchronized {len(users)} users to mail service")
            return True

        except Exception as e:
            self.logger.error(f"Failed to sync users to mail service: {e}")
            return False

    def sync_domains(self, domains: List[DomainConfig]) -> bool:
        """Synchronize domains to Postfix virtual domains."""
        try:
            # Generate virtual domains file
            virtual_domains_content = "\n".join(
                domain.name for domain in domains if domain.enabled
            )
            virtual_domains_path = (
                self.config_manager.paths.state_path / "mail" / "virtual_domains"
            )
            virtual_domains_path.parent.mkdir(parents=True, exist_ok=True)

            with open(virtual_domains_path, "w", encoding="utf-8") as f:
                f.write(virtual_domains_content)

            self.logger.info(f"Synchronized {len(domains)} domains to mail service")
            return True

        except Exception as e:
            self.logger.error(f"Failed to sync domains to mail service: {e}")
            return False

    def _generate_virtual_users(self, users: List[UserConfig]) -> str:
        """Generate Postfix virtual_users file content."""
        lines = []
        for user in users:
            if user.enabled:
                for domain in user.domains:
                    # Map email to mailbox
                    lines.append(f"{user.email} {user.username}@{domain}")
                    # Add alias if username differs from email local part
                    email_local = user.email.split("@")[0]
                    if email_local != user.username:
                        lines.append(
                            f"{user.username}@{domain} {user.username}@{domain}"
                        )
        return "\n".join(lines) + "\n"

    def _generate_dovecot_users(self, users: List[UserConfig]) -> str:
        """Generate Dovecot users file content."""
        lines = []
        for user in users:
            if user.enabled:
                # Dovecot format: user:password:uid:gid:gecos:home:shell:extra
                # Using username as password (would be hashed in production)
                home_dir = f"/var/mail/{user.username}"
                lines.append(
                    f"{user.username}"
                    + ":"
                    + f"{user.username}"
                    + ":"
                    + "1000"
                    + ":"
                    + "1000"
                    + "::"
                    + f"{home_dir}"
                    + "::"
                )
        return "\n".join(lines) + "\n"

    def _create_user_mailboxes(self, users: List[UserConfig]) -> None:
        """Create mailbox directories for users."""
        mailboxes_path = self.config_manager.paths.state_path / "mailboxes"
        mailboxes_path.mkdir(parents=True, exist_ok=True)

        for user in users:
            if user.enabled:
                user_mailbox = mailboxes_path / user.username
                user_mailbox.mkdir(exist_ok=True)

                # Create standard mailbox directories
                for folder in ["INBOX", "Sent", "Drafts", "Trash"]:
                    (user_mailbox / folder).mkdir(exist_ok=True)

    def validate_configuration(self) -> List[str]:
        """Validate mail service configuration."""
        errors = []

        # Check if required files exist
        required_files = [
            self.config_manager.paths.state_path / "mail" / "virtual_users",
            self.config_manager.paths.state_path / "mail" / "virtual_domains",
            self.config_manager.paths.state_path / "mail" / "dovecot_users",
        ]

        for file_path in required_files:
            if not file_path.exists():
                errors.append(f"Required mail config file missing: {file_path}")

        return errors

    def reload_service(self) -> bool:
        """Reload mail service to pick up configuration changes."""
        if not self.container_manager:
            self.logger.warning("No container manager available for service reload")
            return False

        try:
            # Reload Postfix
            postfix_result = self.container_manager.execute_command(
                ["postfix", "reload"]
            )
            if not postfix_result.success:
                self.logger.error(f"Failed to reload Postfix: {postfix_result.stderr}")
                return False

            # Reload Dovecot
            dovecot_result = self.container_manager.execute_command(
                ["doveadm", "reload"]
            )
            if not dovecot_result.success:
                self.logger.error(f"Failed to reload Dovecot: {dovecot_result.stderr}")
                return False

            self.logger.info("Successfully reloaded mail service")
            return True

        except Exception as e:
            self.logger.error(f"Failed to reload mail service: {e}")
            return False

    def delete_user(self, username: str) -> bool:
        """Delete user and their mailbox."""
        try:
            # Remove mailbox directory
            mailbox_path = self.config_manager.paths.state_path / "mailboxes" / username
            if mailbox_path.exists():
                shutil.rmtree(mailbox_path)
                self.logger.info(f"Deleted mailbox for user: {username}")

            # Regenerate configuration files without this user
            current_users = [
                user
                for user in self.config_manager.users_config.users
                if user.username != username
            ]
            self.sync_users(current_users)

            return True

        except Exception as e:
            self.logger.error(f"Failed to delete user {username}: {e}")
            return False


class DnsServiceSynchronizer(ServiceSynchronizer):
    """Synchronizes configuration changes to DNS service (BIND)."""

    def __init__(
        self,
        config_manager: ConfigurationManager,
        container_manager: Optional[ContainerManager] = None,
    ):
        """Initialize DNS service synchronizer."""
        super().__init__(config_manager)
        self.container_manager = container_manager

    def sync_users(self, users: List[UserConfig]) -> bool:
        """DNS service doesn't need user synchronization."""
        return True

    def sync_domains(self, domains: List[DomainConfig]) -> bool:
        """Synchronize domains to BIND zone files."""
        try:
            zones_path = self.config_manager.paths.state_path / "dns-zones"
            zones_path.mkdir(parents=True, exist_ok=True)

            for domain in domains:
                if domain.enabled:
                    zone_file_content = self._generate_zone_file(domain)
                    zone_file_path = zones_path / f"db.{domain.name}"

                    with open(zone_file_path, "w", encoding="utf-8") as f:
                        f.write(zone_file_content)

            # Update BIND configuration to include new zones
            self._update_named_conf(domains)

            self.logger.info(f"Synchronized {len(domains)} domains to DNS service")
            return True

        except Exception as e:
            self.logger.error(f"Failed to sync domains to DNS service: {e}")
            return False

    def _generate_zone_file(self, domain: DomainConfig) -> str:
        """Generate BIND zone file for domain."""
        content = [
            "$TTL 86400",
            f"@   IN  SOA {domain.name}. admin.{domain.name}. (",
            "    2024010101  ; Serial",
            "    3600        ; Refresh",
            "    1800        ; Retry",
            "    604800      ; Expire",
            "    86400 )     ; Minimum TTL",
            "",
        ]

        # Add MX records
        for mx in domain.mx_records:
            content.append(f"@   IN  MX  10  {mx}.")

        # Add A records
        for name, ip in domain.a_records.items():
            content.append(f"{name}   IN  A   {ip}")

        # Add CNAME records
        for alias, target in domain.cname_records.items():
            content.append(f"{alias}   IN  CNAME   {target}")

        # Add TXT records
        for name, txt in domain.txt_records.items():
            content.append(f'{name}   IN  TXT   "{txt}"')

        return "\n".join(content) + "\n"

    def _update_named_conf(self, domains: List[DomainConfig]) -> None:
        """Update BIND named.conf with zone definitions."""
        named_conf_path = (
            self.config_manager.paths.state_path / "dns" / "named.conf.local"
        )
        named_conf_path.parent.mkdir(parents=True, exist_ok=True)

        content = []
        for domain in domains:
            if domain.enabled:
                content.extend(
                    [
                        f'zone "{domain.name}" {{',
                        "    type master;",
                        f'    file "/etc/bind/zones/db.{domain.name}"' + ";",
                        '    allow-update { key "rndc-key"; };',
                        "}};",
                        "",
                    ]
                )

        with open(named_conf_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

    def validate_configuration(self) -> List[str]:
        """Validate DNS service configuration."""
        errors = []

        if not self.container_manager:
            errors.append("No container manager available for DNS validation")
            return errors

        try:
            # Check named configuration
            result = self.container_manager.execute_command(["named-checkconf"])
            if not result.success:
                errors.append(f"BIND configuration error: {result.stderr}")

            # Check zone files
            domains = self.config_manager.domains_config.domains
            for domain in domains:
                if domain.enabled:
                    zone_check = self.container_manager.execute_command(
                        [
                            "named-checkzone",
                            domain.name,
                            f"/etc/bind/zones/db.{domain.name}",
                        ]
                    )
                    if not zone_check.success:
                        errors.append(
                            f"Zone file error for {domain.name}: {zone_check.stderr}"
                        )

        except Exception as e:
            errors.append(f"DNS validation error: {e}")

        return errors

    def reload_service(self) -> bool:
        """Reload DNS service to pick up configuration changes."""
        if not self.container_manager:
            self.logger.warning("No container manager available for service reload")
            return False

        try:
            result = self.container_manager.execute_command(["rndc", "reload"])
            if result.success:
                self.logger.info("Successfully reloaded DNS service")
                return True
            else:
                self.logger.error(f"Failed to reload DNS service: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to reload DNS service: {e}")
            return False


class ApacheServiceSynchronizer(ServiceSynchronizer):
    """Synchronizes configuration changes to Apache service (WebDAV)."""

    def __init__(
        self,
        config_manager: ConfigurationManager,
        container_manager: Optional[ContainerManager] = None,
        skip_reload: bool = False,
    ):
        """Initialize Apache service synchronizer.

        Args:
            config_manager: Configuration manager instance
            container_manager: Container manager for executing commands
            skip_reload: Skip Apache reload for testing environments (default: False)
        """
        super().__init__(config_manager)
        self.container_manager = container_manager
        self.skip_reload = skip_reload

    def sync_users(self, users: List[UserConfig]) -> bool:
        """Synchronize WebDAV users to Apache authentication."""
        try:
            # Only sync users that have webdav service enabled
            webdav_users = [user for user in users if "webdav" in user.services]

            if not webdav_users:
                self.logger.info("No users with WebDAV service enabled")
                return True

            # Sync WebDAV authentication by executing commands in the container
            if self.container_manager:
                return self._sync_webdav_authentication(webdav_users)
            else:
                self.logger.warning(
                    "Apache container manager not available, WebDAV sync skipped"
                )
                return True

        except Exception as e:
            self.logger.error(f"Failed to sync users to Apache service: {e}")
            return False

    def sync_domains(self, domains: List[DomainConfig]) -> bool:
        """Apache service doesn't need domain synchronization for WebDAV."""
        return True

    def validate_configuration(self) -> List[str]:
        """Validate Apache configuration."""
        errors = []
        try:
            if self.container_manager:
                # Test Apache configuration syntax
                result = self.container_manager.execute_command(
                    ["/usr/sbin/apache2ctl", "configtest"]
                )
                if not result.success:
                    errors.append(f"Apache configuration test failed: {result.stderr}")
        except Exception as e:
            errors.append(f"Failed to validate Apache configuration: {e}")

        return errors

    def reload_service(self) -> bool:
        """Reload Apache service to pick up configuration changes."""
        try:
            if not self.container_manager:
                self.logger.warning(
                    "Apache container manager not available, cannot reload"
                )
                return False

            # Graceful Apache reload
            result = self.container_manager.execute_command(
                ["/usr/sbin/apache2ctl", "graceful"]
            )

            if result.success:
                self.logger.info("Successfully reloaded Apache service")
                return True
            else:
                self.logger.error(f"Failed to reload Apache service: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to reload Apache service: {e}")
            return False

    def _sync_webdav_authentication(self, webdav_users: List[UserConfig]) -> bool:
        """Sync WebDAV authentication by updating htdigest file."""
        if not self.container_manager:
            self.logger.error("Container manager not available for WebDAV sync")
            return False

        try:
            # Optimize for tests: build htdigest content locally and write once
            htdigest_lines = []

            for user in webdav_users:
                password = self._get_user_webdav_password(user.username)
                if password:
                    # Calculate MD5 hash for digest auth
                    import hashlib

                    realm = "WebDAV Secure Area"
                    ha1 = hashlib.md5(  # nosec B324
                        (
                            f"{user.username}" + ":" + f"{realm}" + ":" + f"{password}"
                        ).encode()
                    ).hexdigest()
                    htdigest_lines.append(
                        f"{user.username}" + ":" + f"{realm}" + ":" + f"{ha1}"
                    )
                else:
                    self.logger.warning(
                        f"No password available for WebDAV user: {user.username}"
                    )

            if htdigest_lines:
                # Write all users in a single command for better performance
                htdigest_content = "\\n".join(htdigest_lines)
                write_cmd = [
                    "bash",
                    "-c",
                    f'printf "{htdigest_content}\\n" > /etc/apache2/.webdav-digest',
                ]

                result = self.container_manager.execute_command(write_cmd)

                if result.success:
                    self.logger.info(
                        f"Updated WebDAV authentication for {len(htdigest_lines)} users"
                    )

                    # Apache reload is required in production for changes to take effect
                    # Skip reload only for testing environments to improve performance
                    if self.skip_reload:
                        self.logger.debug("Skipping Apache reload (testing mode)")
                        return True
                    else:
                        return self.reload_service()
                else:
                    self.logger.error(
                        f"Failed to write WebDAV auth file: {result.stderr}"
                    )
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Failed to sync WebDAV authentication: {e}")
            return False

    def _get_user_webdav_password(self, username: str) -> Optional[str]:
        """Get WebDAV password for user from secrets system."""
        try:
            from .secrets import PasswordManager

            secrets_file = self.config_manager.paths.config_path / "secrets.yaml"
            password_manager = PasswordManager(secrets_file)

            return password_manager.get_user_password_for_service(username, "webdav")
        except Exception as e:
            self.logger.error(f"Failed to get WebDAV password for {username}: {e}")
            return None


class ConfigurationSyncManager:
    """Manages configuration synchronization across all services."""

    def __init__(self, config_manager: ConfigurationManager):
        """Initialize sync manager."""
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.synchronizers: Dict[str, ServiceSynchronizer] = {}

    def register_synchronizer(
        self, service_name: str, synchronizer: ServiceSynchronizer
    ) -> None:
        """Register a service synchronizer."""
        self.synchronizers[service_name] = synchronizer
        self.logger.info(f"Registered synchronizer for {service_name}")

    def sync_all_users(self) -> bool:
        """Synchronize users to all services."""
        users = self.config_manager.users_config.users
        success = True

        for service_name, synchronizer in self.synchronizers.items():
            try:
                if not synchronizer.sync_users(users):
                    self.logger.error(f"Failed to sync users to {service_name}")
                    success = False
            except Exception as e:
                self.logger.error(f"Error syncing users to {service_name}: {e}")
                success = False

        return success

    def sync_all_domains(self) -> bool:
        """Synchronize domains to all services."""
        domains = self.config_manager.domains_config.domains
        success = True

        for service_name, synchronizer in self.synchronizers.items():
            try:
                if not synchronizer.sync_domains(domains):
                    self.logger.error(f"Failed to sync domains to {service_name}")
                    success = False
            except Exception as e:
                self.logger.error(f"Error syncing domains to {service_name}: {e}")
                success = False

        return success

    def validate_all_services(self) -> Dict[str, List[str]]:
        """Validate configuration for all services."""
        validation_results = {}

        for service_name, synchronizer in self.synchronizers.items():
            try:
                errors = synchronizer.validate_configuration()
                validation_results[service_name] = errors
            except Exception as e:
                validation_results[service_name] = [f"Validation error: {e}"]

        return validation_results

    def reload_all_services(self) -> bool:
        """Reload all services to pick up configuration changes."""
        success = True

        for service_name, synchronizer in self.synchronizers.items():
            try:
                if not synchronizer.reload_service():
                    self.logger.error(f"Failed to reload {service_name}")
                    success = False
            except Exception as e:
                self.logger.error(f"Error reloading {service_name}: {e}")
                success = False

        return success

    def add_user(self, user: UserConfig) -> bool:
        """Add a new user and synchronize to all services."""
        try:
            # Add user to configuration
            current_users = self.config_manager.users_config
            current_users.users.append(user)
            self.config_manager.save_users_config(current_users)

            # Sync to services
            if self.sync_all_users():
                self.logger.info(f"Successfully added user: {user.username}")
                return True
            else:
                # Rollback on failure
                current_users.users.remove(user)
                self.config_manager.save_users_config(current_users)
                self.logger.error(f"Failed to add user {user.username}, rolled back")
                return False

        except Exception as e:
            self.logger.error(f"Error adding user {user.username}: {e}")
            return False

    def delete_user(self, username: str) -> bool:
        """Delete a user and synchronize to all services."""
        try:
            # Find and remove user from configuration
            current_users = self.config_manager.users_config
            user_to_delete = None

            for user in current_users.users:
                if user.username == username:
                    user_to_delete = user
                    break

            if not user_to_delete:
                self.logger.warning(
                    f"User {username} not found in configuration"  # noqa: E713
                )
                return False

            current_users.users.remove(user_to_delete)
            self.config_manager.save_users_config(current_users)

            # Delete from services (including mailboxes)
            success = True
            for service_name, synchronizer in self.synchronizers.items():
                if hasattr(synchronizer, "delete_user"):
                    if not synchronizer.delete_user(username):
                        success = False

            if success:
                self.logger.info(f"Successfully deleted user: {username}")
            else:
                self.logger.error(
                    f"Some errors occurred while deleting user: {username}"
                )

            return success

        except Exception as e:
            self.logger.error(f"Error deleting user {username}: {e}")
            return False
