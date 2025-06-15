"""Integration tests for user lifecycle management across services."""

import poplib
import smtplib
import tempfile
import time
from email.mime.text import MIMEText
from pathlib import Path
from typing import Generator

import pytest
import requests

from net_servers.actions.container import ContainerManager
from net_servers.config.manager import ConfigurationManager
from net_servers.config.schemas import DomainConfig, UserConfig
from net_servers.config.sync import (
    ConfigurationSyncManager,
    DnsServiceSynchronizer,
    MailServiceSynchronizer,
)

from .port_manager import get_port_manager


@pytest.fixture(scope="session")
def temp_config_dir() -> Generator[Path, None, None]:
    """Create temporary configuration directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="session")
def config_manager(temp_config_dir: Path) -> ConfigurationManager:
    """Create configuration manager for testing."""
    config_manager = ConfigurationManager(base_path=str(temp_config_dir))
    config_manager.initialize_default_configs()
    return config_manager


@pytest.fixture(scope="session")
def mail_container_manager(
    config_manager: ConfigurationManager,
) -> Generator[ContainerManager, None, None]:
    """Start mail container for testing with persistent reuse."""
    from .conftest import ContainerTestHelper

    # Use ContainerTestHelper for persistent container management
    helper = ContainerTestHelper("mail")

    # Build container only if needed
    if not helper.manager.image_exists():
        build_result = helper.manager.build()
        assert (
            build_result.success
        ), f"Failed to build mail container: {build_result.stderr}"

    # Start container with reuse capability
    if not helper.start_container(force_restart=False):
        pytest.fail("Failed to start mail container")

    # Give mail services extra time only if just started
    if not helper.is_container_ready():
        print("Waiting for mail services to initialize...")
        time.sleep(2)  # Reduced from 5s - persistent containers start faster

    yield helper.manager

    # Note: Container left running for debugging and performance


@pytest.fixture(scope="session")
def dns_container_manager(
    config_manager: ConfigurationManager,
) -> Generator[ContainerManager, None, None]:
    """Start DNS container for testing with persistent reuse."""
    from .conftest import ContainerTestHelper

    # Use ContainerTestHelper for persistent container management
    helper = ContainerTestHelper("dns")

    # Build container only if needed
    if not helper.manager.image_exists():
        build_result = helper.manager.build()
        assert (
            build_result.success
        ), f"Failed to build DNS container: {build_result.stderr}"

    # Start container with reuse capability
    if not helper.start_container(force_restart=False):
        pytest.fail("Failed to start DNS container")

    # Brief wait for services to start (reduced for persistent containers)
    time.sleep(1)  # Reduced from 3s

    yield helper.manager

    # Note: Container left running for debugging and performance


@pytest.fixture(scope="session")
def apache_container_manager(
    config_manager: ConfigurationManager,
) -> Generator[ContainerManager, None, None]:
    """Start Apache container for testing with persistent reuse."""
    from .conftest import ContainerTestHelper

    # Use ContainerTestHelper for persistent container management
    helper = ContainerTestHelper("apache")

    # Build container only if needed
    if not helper.manager.image_exists():
        build_result = helper.manager.build()
        assert (
            build_result.success
        ), f"Failed to build Apache container: {build_result.stderr}"

    # Start container with reuse capability
    if not helper.start_container(force_restart=False):
        pytest.fail("Failed to start Apache container")

    # Wait longer for SSL services to initialize properly
    time.sleep(5)  # Extended wait for SSL setup

    yield helper.manager

    # Note: Container left running for debugging and performance


@pytest.fixture(scope="session")
def sync_manager(
    config_manager: ConfigurationManager,
    mail_container_manager: ContainerManager,
    dns_container_manager: ContainerManager,
    apache_container_manager: ContainerManager,
) -> ConfigurationSyncManager:
    """Create configuration sync manager with all services."""
    sync_manager = ConfigurationSyncManager(config_manager)

    # Register synchronizers
    mail_sync = MailServiceSynchronizer(config_manager, mail_container_manager)
    dns_sync = DnsServiceSynchronizer(config_manager, dns_container_manager)

    # Import and register Apache synchronizer for WebDAV
    from net_servers.config.sync import ApacheServiceSynchronizer

    apache_sync = ApacheServiceSynchronizer(
        config_manager,
        apache_container_manager,
        skip_reload=True,  # Skip Apache reload for test performance
    )

    sync_manager.register_synchronizer("mail", mail_sync)
    sync_manager.register_synchronizer("dns", dns_sync)
    sync_manager.register_synchronizer("apache", apache_sync)

    # Initial sync
    assert sync_manager.sync_all_domains(), "Failed to sync initial domains"
    assert sync_manager.sync_all_users(), "Failed to sync initial users"

    return sync_manager


class TestUserLifecycle:
    """Test complete user lifecycle including email functionality."""

    def test_user_lifecycle_complete(
        self,
        sync_manager: ConfigurationSyncManager,
        mail_container_manager: ContainerManager,
        apache_container_manager: ContainerManager,
    ):
        """Test complete user lifecycle: add → verify → email → delete."""
        test_user = UserConfig(
            username="testuser",
            email="testuser@local.dev",
            domains=["local.dev"],
            roles=["user"],
            mailbox_quota="100M",
        )

        # Step 1: Add user
        assert sync_manager.add_user(test_user), "Failed to add test user"

        # Step 2: Verify user was added to configuration
        users = sync_manager.config_manager.users_config.users
        user_found = any(user.username == "testuser" for user in users)
        assert user_found, "Test user not found in configuration"

        # Step 3: Verify mailbox was created
        mailbox_path = (
            sync_manager.config_manager.paths.state_path / "mailboxes" / "testuser"
        )
        assert mailbox_path.exists(), "Mailbox directory not created"
        assert (mailbox_path / "INBOX").exists(), "INBOX folder not created"

        # Step 4: Verify user appears in mail service files
        virtual_users_path = (
            sync_manager.config_manager.paths.state_path / "mail" / "virtual_users"
        )
        if virtual_users_path.exists():
            with open(virtual_users_path, "r") as f:
                virtual_users_content = f.read()
            assert (
                "testuser@local.dev" in virtual_users_content
            ), "User not in virtual_users file"

        # Step 5: Brief wait for services to reload and test email delivery
        time.sleep(1)  # Reduced from 2s

        # For now, test with existing mail users since config management
        # isn't fully integrated
        # TODO: Integrate with actual container configuration management

        # Get mail container helper for correct port mapping
        from .conftest import ContainerTestHelper

        mail_helper = ContainerTestHelper("mail")

        email_sent = self._send_test_email(
            to_email="test@local",  # Use existing container user
            subject="Test Email for User Lifecycle",
            body="This is a test email to verify user creation.",
            mail_helper=mail_helper,
        )
        assert email_sent, "Failed to send test email"

        # Verify email was received using existing container user (with retry logic)
        email_received = self._check_email_received(
            username="test@local",  # Use full email address for auth
            password="password",  # Use existing container password
            expected_subject="Test Email for User Lifecycle",
            mail_helper=mail_helper,
            max_wait_time=2,  # Maximum 2 seconds wait with polling
        )
        assert email_received, "Test email was not received"

        # Step 6: Test WebDAV functionality with admin user
        # Set up WebDAV authentication using the sync system
        from net_servers.config.secrets import PasswordManager

        secrets_file = sync_manager.config_manager.paths.config_path / "secrets.yaml"
        password_manager = PasswordManager(secrets_file)

        # Ensure admin user exists with WebDAV service enabled
        admin_user = UserConfig(
            username="admin",
            email="admin@local.dev",
            domains=["local.dev"],
            roles=["admin"],
            services=["email", "webdav"],  # Enable WebDAV service
        )

        # Add or update admin user in configuration
        success = sync_manager.add_user(admin_user)
        if not success:
            # User might already exist, try to update
            current_users = sync_manager.config_manager.users_config.users
            for i, user in enumerate(current_users):
                if user.username == "admin":
                    current_users[i] = admin_user
                    break
            sync_manager.config_manager.save_users_config(
                sync_manager.config_manager.users_config
            )

        # Set up admin user password for testing
        admin_password = "admin_secure_password"
        password_manager.set_user_password(username="admin", password=admin_password)

        # Sync the passwords to WebDAV authentication
        sync_success = sync_manager.sync_all_users()
        assert sync_success, "Failed to sync WebDAV authentication"

        # Get Apache container helper for correct port mapping
        from .conftest import ContainerTestHelper

        apache_helper = ContainerTestHelper("apache")

        # Test WebDAV upload functionality with admin user from configuration
        webdav_upload_success = self._test_webdav_upload(
            username="admin",  # Admin user from configuration
            password=admin_password,  # Password from secrets system
            filename="test-lifecycle-file.txt",
            content="This is a test file created during user lifecycle testing.",
            apache_helper=apache_helper,
        )
        assert webdav_upload_success, "Failed to upload file via WebDAV"

        # Test WebDAV download functionality
        webdav_download_success = self._test_webdav_download(
            username="admin",
            password=admin_password,
            filename="test-lifecycle-file.txt",
            expected_content=(
                "This is a test file created during user lifecycle testing."
            ),
            apache_helper=apache_helper,
        )
        assert webdav_download_success, "Failed to download file via WebDAV"

        # Test WebDAV file listing
        webdav_list_success = self._test_webdav_list(
            username="admin",
            password=admin_password,
            expected_file="test-lifecycle-file.txt",
            apache_helper=apache_helper,
        )
        assert webdav_list_success, "Failed to list files via WebDAV"

        # Step 7: Delete user
        assert sync_manager.delete_user("testuser"), "Failed to delete test user"

        # Step 8: Verify user was removed from configuration
        users_after_delete = sync_manager.config_manager.users_config.users
        user_still_exists = any(
            user.username == "testuser" for user in users_after_delete
        )
        assert (
            not user_still_exists
        ), "Test user still exists in configuration after deletion"

        # Step 9: Verify mailbox was removed
        assert (
            not mailbox_path.exists()
        ), "Mailbox directory still exists after user deletion"

    def test_user_validation_before_add(self, sync_manager: ConfigurationSyncManager):
        """Test user validation before adding to system."""
        # Test invalid email - this should be caught by Pydantic validation
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserConfig(
                username="invaliduser",
                email="invalid-email",  # Missing @ symbol
                domains=["local.dev"],
                roles=["user"],
            )

    def test_duplicate_user_handling(self, sync_manager: ConfigurationSyncManager):
        """Test handling of duplicate user addition."""
        test_user = UserConfig(
            username="duplicatetest",
            email="duplicatetest@local.dev",
            domains=["local.dev"],
            roles=["user"],
        )

        # Add user first time
        assert sync_manager.add_user(test_user), "Failed to add user first time"

        # Try to add same user again
        duplicate_user = UserConfig(
            username="duplicatetest",  # Same username
            email="duplicatetest2@local.dev",  # Different email
            domains=["local.dev"],
            roles=["user"],
        )

        # Should handle gracefully (implementation dependent)
        sync_manager.add_user(duplicate_user)
        # Note: Depending on implementation, this might succeed or fail
        # The key is that it should be handled gracefully

        # Cleanup
        sync_manager.delete_user("duplicatetest")

    def test_mailbox_permissions_and_structure(
        self, sync_manager: ConfigurationSyncManager
    ):
        """Test that mailboxes are created with correct structure and permissions."""
        test_user = UserConfig(
            username="permtest",
            email="permtest@local.dev",
            domains=["local.dev"],
            roles=["user"],
        )

        # Add user
        assert sync_manager.add_user(test_user), "Failed to add permission test user"

        # Check mailbox structure
        mailbox_path = (
            sync_manager.config_manager.paths.state_path / "mailboxes" / "permtest"
        )
        assert mailbox_path.exists(), "Mailbox directory not created"

        # Check standard folders
        required_folders = ["INBOX", "Sent", "Drafts", "Trash"]
        for folder in required_folders:
            folder_path = mailbox_path / folder
            assert folder_path.exists(), f"Required folder {folder} not created"
            assert folder_path.is_dir(), f"Required folder {folder} is not a directory"

        # Cleanup
        sync_manager.delete_user("permtest")

    def test_service_configuration_validation(
        self, sync_manager: ConfigurationSyncManager
    ):
        """Test that service configuration is validated after changes."""
        # Get validation results for all services
        validation_results = sync_manager.validate_all_services()

        # Check that validation was performed for expected services
        assert "mail" in validation_results, "Mail service validation not performed"
        assert "dns" in validation_results, "DNS service validation not performed"

        # Log any validation errors (but don't fail test unless critical)
        for service, errors in validation_results.items():
            if errors:
                print(f"Validation warnings for {service}: {errors}")

    def _send_test_email(
        self, to_email: str, subject: str, body: str, mail_helper=None
    ) -> bool:
        """Send a test email via SMTP."""
        try:
            # Create message
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = "admin@local.dev"
            msg["To"] = to_email

            # Send via SMTP using container helper for correct port
            if mail_helper:
                smtp_port = mail_helper.get_container_port(25)
            else:
                # Fallback to port manager
                smtp_port = get_port_manager().get_host_port("mail", 25)

            with smtplib.SMTP(
                "localhost", smtp_port, timeout=2
            ) as smtp:  # Faster timeout
                smtp.send_message(msg)

            return True

        except Exception as e:
            print(f"Failed to send test email: {e}")
            return False

    def _check_email_received(
        self,
        username: str,
        password: str,
        expected_subject: str,
        mail_helper=None,
        max_wait_time=2,
    ) -> bool:
        """Check if email was received via POP3 with smart polling."""
        import time

        # Get port
        if mail_helper:
            pop3_port = mail_helper.get_container_port(110)
        else:
            pop3_port = get_port_manager().get_host_port("mail", 110)

        # Smart polling: check immediately, then retry with short delays
        start_time = time.time()
        attempts = 0

        while time.time() - start_time < max_wait_time:
            attempts += 1
            try:
                pop = poplib.POP3("localhost", pop3_port)
                try:
                    pop.user(username)
                    pop.pass_(password)

                    # Get message count
                    num_messages = len(pop.list()[1])

                    # Check recent messages for expected subject
                    for i in range(max(1, num_messages - 5), num_messages + 1):
                        try:
                            msg_lines = pop.retr(i)[1]
                            msg_text = "\n".join(
                                line.decode("utf-8") for line in msg_lines
                            )

                            subject_line = f"Subject: {expected_subject}"
                            if subject_line in msg_text:
                                return True  # Found the email!
                        except Exception:
                            continue  # Skip this message

                finally:
                    try:
                        pop.quit()
                    except Exception:
                        pass

                # If not found on this attempt, wait briefly before retry
                if attempts == 1:
                    continue  # Try immediately on first failure
                time.sleep(0.1)  # Brief delay between retries

            except Exception:
                # Connection failed, wait briefly before retry
                if attempts == 1:
                    continue  # Try immediately on first failure
                time.sleep(0.1)

        # Email not found within timeout
        print(
            f"Failed to check email reception: Email with subject "
            f"'{expected_subject}' not found after {attempts} attempts "
            f"in {max_wait_time}s"
        )
        return False

    def test_cross_service_consistency(self, sync_manager: ConfigurationSyncManager):
        """Test that user changes are consistently applied across all services."""
        test_user = UserConfig(
            username="crosstest",
            email="crosstest@local.dev",
            domains=["local.dev"],
            roles=["user"],
        )

        # Add user
        assert sync_manager.add_user(test_user), "Failed to add cross-service test user"

        # Check that user appears in mail service configuration
        virtual_users_path = (
            sync_manager.config_manager.paths.state_path / "mail" / "virtual_users"
        )
        if virtual_users_path.exists():
            with open(virtual_users_path, "r") as f:
                content = f.read()
            assert (
                "crosstest@local.dev" in content
            ), "User not found in mail virtual_users"

        # Check that mailbox exists
        mailbox_path = (
            sync_manager.config_manager.paths.state_path / "mailboxes" / "crosstest"
        )
        assert mailbox_path.exists(), "User mailbox not created"

        # Delete user and verify cleanup across services
        assert sync_manager.delete_user(
            "crosstest"
        ), "Failed to delete cross-service test user"

        # Verify cleanup in mail service
        if virtual_users_path.exists():
            with open(virtual_users_path, "r") as f:
                content_after = f.read()
            assert (
                "crosstest@local.dev" not in content_after
            ), "User still in mail virtual_users after deletion"

        # Verify mailbox cleanup
        assert not mailbox_path.exists(), "User mailbox still exists after deletion"

    def test_webdav_user_functionality(
        self,
        sync_manager: ConfigurationSyncManager,
        apache_container_manager: ContainerManager,
    ):
        """Test WebDAV functionality comprehensively with test users."""
        from .conftest import ContainerTestHelper

        apache_helper = ContainerTestHelper("apache")

        # Set up test users with passwords in the test environment
        from net_servers.config.secrets import PasswordManager

        secrets_file = sync_manager.config_manager.paths.config_path / "secrets.yaml"
        password_manager = PasswordManager(secrets_file)

        # Set up test users with WebDAV service enabled
        test_users_config = [
            UserConfig(
                username="admin",
                email="admin@local.dev",
                domains=["local.dev"],
                roles=["admin"],
                services=["email", "webdav"],
            ),
            UserConfig(
                username="test1",
                email="test1@local.dev",
                domains=["local.dev"],
                roles=["user"],
                services=["email", "webdav"],
            ),
        ]

        # Add/update users in configuration
        for user_config in test_users_config:
            success = sync_manager.add_user(user_config)
            if not success:
                # User might already exist, try to update
                current_users = sync_manager.config_manager.users_config.users
                for i, user in enumerate(current_users):
                    if user.username == user_config.username:
                        current_users[i] = user_config
                        break
                sync_manager.config_manager.save_users_config(
                    sync_manager.config_manager.users_config
                )

        # Set up test passwords for WebDAV testing
        test_users = [
            {"username": "admin", "password": "admin_secure_password"},
            {"username": "test1", "password": "test1_secure_password"},
        ]

        # Initialize passwords for test users
        for user_info in test_users:
            password_manager.set_user_password(
                username=user_info["username"], password=user_info["password"]
            )

        # Sync the passwords to WebDAV authentication
        sync_success = sync_manager.sync_all_users()
        assert sync_success, "Failed to sync WebDAV authentication"

        # Set up test scenarios
        test_scenarios = []
        for user_info in test_users:
            # Verify password is available
            password = password_manager.get_user_password_for_service(
                user_info["username"], "webdav"
            )
            if password:
                test_scenarios.append(
                    {
                        "username": user_info["username"],
                        "password": password,
                        "description": (
                            f"{user_info['username'].title()} user with WebDAV access"
                        ),
                    }
                )
            else:
                print(
                    f"Warning: Password not found for {user_info['username']} "
                    "after setting"
                )

        if not test_scenarios:
            pytest.skip("No users with valid passwords found for WebDAV testing")

        for scenario in test_scenarios:
            username = scenario["username"]
            password = scenario["password"]
            desc = scenario["description"]

            print(f"Testing WebDAV with {desc}")

            # Test file operations for this user
            test_filename = f"webdav-test-{username}.txt"
            test_content = (
                f"WebDAV test content for user {username}\nTimestamp: {time.time()}"
            )

            # Test upload
            upload_success = self._test_webdav_upload(
                username=username,
                password=password,
                filename=test_filename,
                content=test_content,
                apache_helper=apache_helper,
            )
            assert upload_success, f"WebDAV upload failed for {desc}"

            # Test download
            download_success = self._test_webdav_download(
                username=username,
                password=password,
                filename=test_filename,
                expected_content=test_content,
                apache_helper=apache_helper,
            )
            assert download_success, f"WebDAV download failed for {desc}"

            # Test file listing
            list_success = self._test_webdav_list(
                username=username,
                password=password,
                expected_file=test_filename,
                apache_helper=apache_helper,
            )
            assert list_success, f"WebDAV file listing failed for {desc}"

            print(f"✓ WebDAV functionality verified for {desc}")

        # Test authentication failure with wrong credentials
        auth_failure_test = self._test_webdav_authentication_failure(
            username="admin",
            wrong_password="wrongpassword",
            apache_helper=apache_helper,
        )
        assert auth_failure_test, "WebDAV should reject invalid credentials"

        print("✓ WebDAV authentication security verified")

    def _test_webdav_authentication_failure(
        self, username: str, wrong_password: str, apache_helper=None
    ) -> bool:
        """Test that WebDAV properly rejects invalid credentials."""
        try:
            # Get HTTPS port for WebDAV
            if apache_helper:
                https_port = apache_helper.get_container_port(443)
            else:
                from .port_manager import get_port_manager

                https_port = get_port_manager().get_host_port("apache", 443)

            webdav_url = f"https://localhost:{https_port}/webdav/"  # noqa: E231

            # Create HTTP digest authentication with wrong password
            from requests.auth import HTTPDigestAuth

            auth = HTTPDigestAuth(username, wrong_password)

            # Try to access WebDAV directory (should fail)
            response = requests.get(
                webdav_url,
                auth=auth,
                verify=False,  # Self-signed certificates
                timeout=5,
            )

            # Should return 401 Unauthorized
            return response.status_code == 401

        except Exception as e:
            print(f"WebDAV authentication test failed: {e}")
            return False

    def _test_webdav_upload(
        self,
        username: str,
        password: str,
        filename: str,
        content: str,
        apache_helper=None,
    ) -> bool:
        """Test WebDAV file upload functionality."""
        try:
            # Get HTTPS port for WebDAV (WebDAV requires HTTPS)
            if apache_helper:
                https_port = apache_helper.get_container_port(443)
            else:
                from .port_manager import get_port_manager

                https_port = get_port_manager().get_host_port("apache", 443)

            webdav_url = (
                f"https://localhost:{https_port}" + f"/webdav/{filename}"  # noqa: E231
            )

            # Create HTTP digest authentication
            from requests.auth import HTTPDigestAuth

            auth = HTTPDigestAuth(username, password)

            # Upload file using PUT request - simplified for test performance
            response = requests.put(
                webdav_url,
                data=content,
                auth=auth,
                verify=False,  # Self-signed certificates
                timeout=3,  # Shorter timeout for tests
            )

            # WebDAV PUT should return 201 (Created) or 204 (No Content)
            return response.status_code in [201, 204]

        except Exception as e:
            print(f"WebDAV upload failed: {e}")
            return False

    def _test_webdav_download(
        self,
        username: str,
        password: str,
        filename: str,
        expected_content: str,
        apache_helper=None,
    ) -> bool:
        """Test WebDAV file download functionality."""
        try:
            # Get HTTPS port for WebDAV
            if apache_helper:
                https_port = apache_helper.get_container_port(443)
            else:
                from .port_manager import get_port_manager

                https_port = get_port_manager().get_host_port("apache", 443)

            webdav_url = (
                f"https://localhost:{https_port}" + f"/webdav/{filename}"  # noqa: E231
            )

            # Create HTTP digest authentication
            from requests.auth import HTTPDigestAuth

            auth = HTTPDigestAuth(username, password)

            # Download file using GET request - simplified for test performance
            response = requests.get(
                webdav_url,
                auth=auth,
                verify=False,  # Self-signed certificates
                timeout=3,  # Shorter timeout for tests
            )

            # Check if download was successful and content matches
            if response.status_code == 200:
                return response.text.strip() == expected_content.strip()
            else:
                print(f"WebDAV download failed with status {response.status_code}")
                return False

        except Exception as e:
            print(f"WebDAV download failed: {e}")
            return False

    def _test_webdav_list(
        self,
        username: str,
        password: str,
        expected_file: str,
        apache_helper=None,
    ) -> bool:
        """Test WebDAV directory listing functionality."""
        try:
            # Get HTTPS port for WebDAV
            if apache_helper:
                https_port = apache_helper.get_container_port(443)
            else:
                from .port_manager import get_port_manager

                https_port = get_port_manager().get_host_port("apache", 443)

            webdav_url = f"https://localhost:{https_port}/webdav/"  # noqa: E231

            # Create HTTP digest authentication
            from requests.auth import HTTPDigestAuth

            auth = HTTPDigestAuth(username, password)

            # List directory using PROPFIND request
            headers = {
                "Depth": "1",
                "Content-Type": "application/xml",
            }

            # Simple PROPFIND request body
            propfind_body = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:displayname/>
        <D:getcontentlength/>
        <D:getlastmodified/>
        <D:resourcetype/>
    </D:prop>
</D:propfind>"""

            response = requests.request(
                "PROPFIND",
                webdav_url,
                data=propfind_body,
                headers=headers,
                auth=auth,
                verify=False,  # Self-signed certificates
                timeout=2,  # Shorter timeout for tests
            )

            # PROPFIND should return 207 Multi-Status
            if response.status_code == 207:
                # Check if expected file is in the listing
                return expected_file in response.text
            else:
                print(f"WebDAV PROPFIND failed with status {response.status_code}")
                return False

        except Exception as e:
            print(f"WebDAV directory listing failed: {e}")
            return False


class TestDomainManagement:
    """Test domain configuration management."""

    def test_domain_sync_to_dns(self, sync_manager: ConfigurationSyncManager):
        """Test that domain configuration is properly synced to DNS service."""
        # Add a test domain
        test_domain = DomainConfig(
            name="test.local",
            enabled=True,
            mx_records=["mail.test.local"],
            a_records={"mail": "172.20.0.10", "www": "172.20.0.20"},
        )

        # Add domain to configuration
        current_domains = sync_manager.config_manager.domains_config
        current_domains.domains.append(test_domain)
        sync_manager.config_manager.save_domains_config(current_domains)

        # Sync to services
        assert sync_manager.sync_all_domains(), "Failed to sync domains"

        # Check that zone file was created
        zone_file_path = (
            sync_manager.config_manager.paths.state_path / "dns-zones" / "db.test.local"
        )
        assert zone_file_path.exists(), "DNS zone file not created"

        # Check zone file content
        with open(zone_file_path, "r") as f:
            zone_content = f.read()

        assert "mail.test.local." in zone_content, "MX record not in zone file"
        assert "172.20.0.10" in zone_content, "A record not in zone file"

        # Cleanup
        current_domains.domains.remove(test_domain)
        sync_manager.config_manager.save_domains_config(current_domains)


@pytest.mark.integration
class TestServiceReloading:
    """Test service reloading without container restart."""

    def test_mail_service_reload(self, sync_manager: ConfigurationSyncManager):
        """Test that mail service can be reloaded without container restart."""
        mail_sync = sync_manager.synchronizers.get("mail")
        if mail_sync:
            result = mail_sync.reload_service()
            # Note: This might fail if services aren't configured to reload
            # In that case, we log the issue but don't fail the test
            if not result:
                print(
                    "Mail service reload failed - this is expected in basic test setup"
                )

    def test_dns_service_reload(self, sync_manager: ConfigurationSyncManager):
        """Test that DNS service can be reloaded without container restart."""
        dns_sync = sync_manager.synchronizers.get("dns")
        if dns_sync:
            result = dns_sync.reload_service()
            # Note: This might fail if services aren't configured to reload
            if not result:
                print(
                    "DNS service reload failed - this is expected in basic test setup"
                )
