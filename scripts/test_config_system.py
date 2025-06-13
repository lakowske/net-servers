#!/usr/bin/env python3
"""Configuration system smoke test script.

This script exercises the configuration management system by:
1. Initializing configuration
2. Adding test users and domains
3. Validating sync across services
4. Testing user operations (add/remove)
5. Cleaning up test data
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# flake8: noqa: E402
from net_servers.actions.container import ContainerManager
from net_servers.config.containers import get_container_config
from net_servers.config.manager import ConfigurationManager
from net_servers.config.schemas import DomainConfig, UserConfig
from net_servers.config.sync import (
    ConfigurationSyncManager,
    DnsServiceSynchronizer,
    MailServiceSynchronizer,
)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def print_step(step: str, description: str) -> None:
    """Print a test step with formatting."""
    print(f"\n🔧 Step {step}: {description}")
    print("=" * 60)


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"✅ {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"❌ {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"ℹ️  {message}")


class ConfigSystemTester:
    """Configuration system smoke tester."""

    def __init__(self, base_path: str, use_containers: bool = False):
        """Initialize the tester."""
        self.base_path = Path(base_path)
        self.use_containers = use_containers
        self.config_manager: ConfigurationManager
        self.sync_manager: ConfigurationSyncManager
        self.logger = logging.getLogger(__name__)

        # Test data
        self.test_users = [
            UserConfig(
                username="testuser1",
                email="testuser1@example.com",
                domains=["example.com"],
                roles=["user"],
                mailbox_quota="100M",
            ),
            UserConfig(
                username="testuser2",
                email="testuser2@test.dev",
                domains=["test.dev"],
                roles=["user"],
                mailbox_quota="50M",
            ),
            UserConfig(
                username="admin2",
                email="admin2@example.com",
                domains=["example.com"],
                roles=["admin"],
                mailbox_quota="1G",
            ),
        ]

        self.test_domains = [
            DomainConfig(
                name="example.com",
                enabled=True,
                mx_records=["mail.example.com"],
                a_records={"www": "192.168.1.100", "mail": "192.168.1.101"},
            ),
            DomainConfig(
                name="test.dev",
                enabled=True,
                mx_records=["mail.test.dev"],
                a_records={"@": "192.168.2.100", "mail": "192.168.2.101"},
                txt_records={"@": "v=spf1 mx ~all"},
            ),
        ]

    def step_1_initialize_config(self) -> bool:
        """Step 1: Initialize configuration system."""
        print_step("1", "Initialize Configuration System")

        try:
            # Create base directory
            self.base_path.mkdir(parents=True, exist_ok=True)
            print_info(f"Using configuration path: {self.base_path}")

            # Initialize configuration manager
            self.config_manager = ConfigurationManager(base_path=str(self.base_path))
            self.config_manager.initialize_default_configs()
            print_success("Configuration manager initialized")

            # Initialize sync manager
            self.sync_manager = ConfigurationSyncManager(self.config_manager)
            print_success("Sync manager initialized")

            # Register synchronizers
            if self.use_containers:
                self._setup_container_synchronizers()
            else:
                # Use basic synchronizers for testing
                mail_sync = MailServiceSynchronizer(self.config_manager)
                dns_sync = DnsServiceSynchronizer(self.config_manager)
                self.sync_manager.register_synchronizer("mail", mail_sync)
                self.sync_manager.register_synchronizer("dns", dns_sync)
                print_success("File-based synchronizers registered")

            return True

        except Exception as e:
            print_error(f"Failed to initialize configuration: {e}")
            self.logger.exception("Configuration initialization error")
            return False

    def _setup_container_synchronizers(self) -> None:
        """Set up container-based synchronizers."""
        try:
            # Mail service synchronizer
            mail_config = get_container_config("mail", use_config_manager=True)
            mail_container = ContainerManager(mail_config)
            mail_sync = MailServiceSynchronizer(self.config_manager, mail_container)
            self.sync_manager.register_synchronizer("mail", mail_sync)
            print_success("Mail service synchronizer registered")

            # DNS service synchronizer
            dns_config = get_container_config("dns", use_config_manager=True)
            dns_container = ContainerManager(dns_config)
            dns_sync = DnsServiceSynchronizer(self.config_manager, dns_container)
            self.sync_manager.register_synchronizer("dns", dns_sync)
            print_success("DNS service synchronizer registered")

        except Exception as e:
            print_error(f"Container synchronizer setup failed: {e}")
            # Fall back to file-based synchronizers
            mail_sync = MailServiceSynchronizer(self.config_manager)
            dns_sync = DnsServiceSynchronizer(self.config_manager)
            self.sync_manager.register_synchronizer("mail", mail_sync)
            self.sync_manager.register_synchronizer("dns", dns_sync)
            print_info("Using file-based synchronizers as fallback")

    def step_2_add_domains(self) -> bool:
        """Step 2: Add test domains."""
        print_step("2", "Add Test Domains")

        try:
            for domain in self.test_domains:
                print_info(f"Adding domain: {domain.name}")

                # Add domain to configuration
                domains_config = self.config_manager.domains_config
                domains_config.domains.append(domain)
                self.config_manager.save_domains_config(domains_config)

                # Sync domain to services
                result = self.sync_manager.sync_all_domains()
                if result:
                    print_success(f"Domain {domain.name} added and synced")
                else:
                    print_error(f"Domain {domain.name} sync failed")
                    return False

            return True

        except Exception as e:
            print_error(f"Failed to add domains: {e}")
            self.logger.exception("Domain addition error")
            return False

    def step_3_add_users(self) -> bool:
        """Step 3: Add test users."""
        print_step("3", "Add Test Users")

        try:
            for user in self.test_users:
                print_info(f"Adding user: {user.username} ({user.email})")

                result = self.sync_manager.add_user(user)
                if result:
                    print_success(f"User {user.username} added successfully")

                    # Verify mailbox creation
                    mailbox_path = (
                        self.config_manager.paths.state_path
                        / "mailboxes"
                        / user.username
                    )
                    if mailbox_path.exists():
                        print_success(f"Mailbox created at {mailbox_path}")
                    else:
                        print_error(f"Mailbox not found at {mailbox_path}")

                else:
                    print_error(f"Failed to add user {user.username}")
                    return False

            return True

        except Exception as e:
            print_error(f"Failed to add users: {e}")
            self.logger.exception("User addition error")
            return False

    def step_4_validate_sync(self) -> bool:
        """Step 4: Validate configuration sync."""
        print_step("4", "Validate Configuration Sync")

        try:
            # Validate all services
            validation_results = self.sync_manager.validate_all_services()

            all_valid = True
            for service, errors in validation_results.items():
                if errors:
                    print_error(f"Service {service} validation errors:")
                    for error in errors:
                        print(f"  - {error}")
                    all_valid = False
                else:
                    print_success(f"Service {service} validation passed")

            # Check file creation
            self._verify_generated_files()

            return all_valid

        except Exception as e:
            print_error(f"Validation failed: {e}")
            self.logger.exception("Validation error")
            return False

    def _verify_generated_files(self) -> None:
        """Verify that expected configuration files were generated."""
        print_info("Checking generated configuration files...")

        # Mail service files
        mail_dir = self.config_manager.paths.state_path / "mail"
        expected_mail_files = ["virtual_users", "virtual_domains", "dovecot_users"]

        for filename in expected_mail_files:
            file_path = mail_dir / filename
            if file_path.exists():
                print_success(f"Mail file exists: {filename}")
                # Show content preview
                with open(file_path) as f:
                    content = f.read().strip()
                    lines = content.split("\n")
                    preview = lines[0] if lines else "(empty)"
                    print(f"  Content preview: {preview}")
            else:
                print_error(f"Missing mail file: {filename}")

        # DNS zone files
        dns_dir = self.config_manager.paths.state_path / "dns-zones"
        if dns_dir.exists():
            zone_files = list(dns_dir.glob("db.*"))
            if zone_files:
                print_success(f"DNS zone files created: {len(zone_files)} zones")
                for zone_file in zone_files:
                    print(f"  - {zone_file.name}")
            else:
                print_error("No DNS zone files found")
        else:
            print_error("DNS zones directory not created")

    def step_5_test_user_operations(self) -> bool:
        """Step 5: Test user lifecycle operations."""
        print_step("5", "Test User Lifecycle Operations")

        try:
            # List current users
            current_users = self.config_manager.users_config.users
            initial_count = len(current_users)
            print_info(f"Current user count: {initial_count}")

            # Remove a test user
            user_to_remove = "testuser2"
            print_info(f"Removing user: {user_to_remove}")

            result = self.sync_manager.delete_user(user_to_remove)
            if result:
                print_success(f"User {user_to_remove} removed successfully")

                # Verify removal
                updated_users = self.config_manager.users_config.users
                final_count = len(updated_users)
                if final_count == initial_count - 1:
                    print_success(f"User count updated: {final_count}")
                else:
                    print_error(f"Unexpected user count: {final_count}")
                    return False

                # Check user not in list
                if not any(user.username == user_to_remove for user in updated_users):
                    print_success("User removed from configuration")
                else:
                    print_error("User still in configuration")
                    return False

            else:
                print_error(f"Failed to remove user {user_to_remove}")
                return False

            # Re-sync after removal
            sync_result = self.sync_manager.sync_all_users()
            if sync_result:
                print_success("User sync after removal completed")
            else:
                print_error("User sync after removal failed")
                return False

            return True

        except Exception as e:
            print_error(f"User operations failed: {e}")
            self.logger.exception("User operations error")
            return False

    def step_6_final_validation(self) -> bool:
        """Step 6: Final system validation."""
        print_step("6", "Final System Validation")

        try:
            # Final configuration state
            users = self.config_manager.users_config.users
            domains = self.config_manager.domains_config.domains

            print_info(f"Final user count: {len(users)}")
            print_info(f"Final domain count: {len(domains)}")

            # List remaining users
            print_info("Remaining users:")
            for user in users:
                print(f"  - {user.username} ({user.email})")

            # List domains
            print_info("Configured domains:")
            for domain in domains:
                status = "enabled" if domain.enabled else "disabled"
                print(f"  - {domain.name} ({status})")

            # Final validation
            validation_results = self.sync_manager.validate_all_services()
            all_valid = all(not errors for errors in validation_results.values())

            if all_valid:
                print_success("All services validation passed")
            else:
                print_error("Some services have validation errors")

            return all_valid

        except Exception as e:
            print_error(f"Final validation failed: {e}")
            self.logger.exception("Final validation error")
            return False

    def run_smoke_test(self) -> bool:
        """Run the complete smoke test."""
        print("🚀 Configuration System Smoke Test")
        print("=" * 60)
        print(f"Base Path: {self.base_path}")
        print(f"Use Containers: {self.use_containers}")
        print()

        steps = [
            self.step_1_initialize_config,
            self.step_2_add_domains,
            self.step_3_add_users,
            self.step_4_validate_sync,
            self.step_5_test_user_operations,
            self.step_6_final_validation,
        ]

        for i, step in enumerate(steps, 1):
            if not step():
                print_error(f"Smoke test failed at step {i}")
                return False

        print("\n🎉 Configuration System Smoke Test PASSED")
        print("=" * 60)
        return True

    def cleanup(self) -> None:
        """Clean up test configuration."""
        print_step("Cleanup", "Removing Test Configuration")

        try:
            if self.base_path.exists():
                import shutil

                shutil.rmtree(self.base_path)
                print_success(f"Removed test configuration at {self.base_path}")
            else:
                print_info("No test configuration to clean up")

        except Exception as e:
            print_error(f"Cleanup failed: {e}")
            self.logger.exception("Cleanup error")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Configuration system smoke test")
    parser.add_argument(
        "--base-path",
        default="./test-config",
        help="Base path for test configuration (default: ./test-config)",
    )
    parser.add_argument(
        "--use-containers",
        action="store_true",
        help="Use actual containers for testing (requires running services)",
    )
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Only perform cleanup of test configuration",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    tester = ConfigSystemTester(args.base_path, args.use_containers)

    if args.cleanup_only:
        tester.cleanup()
        return

    try:
        success = tester.run_smoke_test()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        print_info("Running cleanup...")
        tester.cleanup()
        sys.exit(1)

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        logging.exception("Unexpected error")
        print_info("Running cleanup...")
        tester.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()
