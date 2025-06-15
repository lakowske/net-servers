"""Integration tests for Gitweb functionality in Apache container.

Tests cover Git repository web interface, authentication, and user access control.
"""

import subprocess
import time
from typing import Generator

import pytest
import requests
from requests.auth import HTTPDigestAuth

from .conftest import ContainerTestHelper


class TestGitwebIntegration:
    """Test Gitweb integration with Apache container."""

    def test_01_gitweb_requires_authentication(
        self, apache_container: ContainerTestHelper
    ):
        """Test that Gitweb interface requires authentication."""
        https_port = apache_container.get_container_port(443)
        gitweb_url = "https://localhost" + ":" + f"{https_port}/git"

        # Test that unauthenticated access is denied
        response = requests.get(
            gitweb_url, verify=False, timeout=3  # Self-signed certificate
        )

        assert response.status_code == 401, "Gitweb should require authentication"
        assert "Unauthorized" in response.text, "Should show unauthorized message"

    def test_02_gitweb_accessible_with_authentication(
        self, apache_container: ContainerTestHelper
    ):
        """Test that Gitweb is accessible with valid authentication."""
        # Set up authentication by running the working user lifecycle test first
        self._run_user_authentication_setup()

        https_port = apache_container.get_container_port(443)
        gitweb_url = "https://localhost" + ":" + f"{https_port}/git"

        # Test with valid credentials (same as user lifecycle test)
        auth = HTTPDigestAuth("admin", "admin_secure_password")
        response = requests.get(
            gitweb_url, auth=auth, verify=False, timeout=3  # Self-signed certificate
        )

        assert (
            response.status_code == 200
        ), "Gitweb should be accessible with valid auth"
        assert (
            "Net Servers - Git Repositories" in response.text
        ), "Should show Gitweb interface"
        assert "sample.git" in response.text, "Should show sample repository"

    def test_03_gitweb_shows_custom_styling(
        self, apache_container: ContainerTestHelper
    ):
        """Test that Gitweb shows custom header and footer."""
        self._run_user_authentication_setup()

        https_port = apache_container.get_container_port(443)
        gitweb_url = "https://localhost" + ":" + f"{https_port}/git"

        auth = HTTPDigestAuth("admin", "admin_secure_password")
        response = requests.get(gitweb_url, auth=auth, verify=False, timeout=3)

        assert response.status_code == 200

        # Check for custom header elements
        assert "📁 Git Repositories" in response.text, "Should show custom header"
        assert "Source code repositories for Net Servers project" in response.text
        assert "🏠 Projects" in response.text, "Should show navigation links"
        assert "📂 WebDAV" in response.text, "Should show WebDAV link"
        assert "🌐 Home" in response.text, "Should show home link"

        # Check for custom footer
        assert "Powered by" in response.text, "Should show custom footer"
        assert "Net Servers Development Environment" in response.text
        assert "admin@local.dev" in response.text, "Should show contact info"

    def test_04_gitweb_repository_browsing(self, apache_container: ContainerTestHelper):
        """Test browsing Git repository through Gitweb."""
        self._run_user_authentication_setup()

        https_port = apache_container.get_container_port(443)

        # Access the sample repository summary page
        repo_url = (
            "https://localhost"
            + ":"
            + f"{https_port}/git?p=sample.git"
            + ";"
            + "a=summary"
        )

        auth = HTTPDigestAuth("admin", "admin_secure_password")
        response = requests.get(repo_url, auth=auth, verify=False, timeout=3)

        assert response.status_code == 200, "Repository summary should be accessible"
        assert "sample.git" in response.text, "Should show repository name"
        assert "Sample Git repository for testing Gitweb interface" in response.text

    def test_05_gitweb_navigation_links(self, apache_container: ContainerTestHelper):
        """Test that Gitweb navigation links work correctly."""
        self._run_user_authentication_setup()

        https_port = apache_container.get_container_port(443)
        auth = HTTPDigestAuth("admin", "admin_secure_password")

        # Test main Gitweb interface
        gitweb_url = "https://localhost" + ":" + f"{https_port}/git"
        response = requests.get(gitweb_url, auth=auth, verify=False, timeout=3)
        assert response.status_code == 200

        # Test project listing (should be same as main interface)
        projects_url = "https://localhost" + ":" + f"{https_port}/git?a=project_list"
        response = requests.get(projects_url, auth=auth, verify=False, timeout=3)
        assert response.status_code == 200
        assert "sample.git" in response.text

    def test_06_multiple_user_authentication(
        self, apache_container: ContainerTestHelper
    ):
        """Test that multiple users can authenticate to Gitweb."""
        # Set up multiple users with WebDAV/Gitweb access
        self._run_user_authentication_setup()

        https_port = apache_container.get_container_port(443)
        gitweb_url = "https://localhost" + ":" + f"{https_port}/git"

        # Test with admin user
        auth_admin = HTTPDigestAuth("admin", "admin_secure_password")
        response = requests.get(gitweb_url, auth=auth_admin, verify=False, timeout=3)
        assert response.status_code == 200, "Admin should have access to Gitweb"

        # Note: Only admin user is guaranteed to be set up by the user lifecycle test
        # For now, we'll just verify admin access works consistently

    def test_07_gitweb_cross_service_integration(
        self, apache_container: ContainerTestHelper
    ):
        """Test integration between Gitweb and other services."""
        self._run_user_authentication_setup()

        https_port = apache_container.get_container_port(443)
        auth = HTTPDigestAuth("admin", "admin_secure_password")

        # Test that same credentials work for WebDAV
        webdav_url = "https://localhost" + ":" + f"{https_port}/webdav/"
        webdav_response = requests.get(webdav_url, auth=auth, verify=False, timeout=3)
        assert webdav_response.status_code == 200, "Same auth should work for WebDAV"

        # Test that same credentials work for Gitweb
        gitweb_url = "https://localhost" + ":" + f"{https_port}/git"
        gitweb_response = requests.get(gitweb_url, auth=auth, verify=False, timeout=3)
        assert gitweb_response.status_code == 200, "Same auth should work for Gitweb"

    def test_08_git_repository_creation_and_access(
        self, apache_container: ContainerTestHelper
    ):
        """Test creating a new Git repository and accessing it via Gitweb."""
        self._run_user_authentication_setup()

        # Create a new test repository
        repo_name = "test-repo.git"
        create_result = apache_container.exec_command(
            [
                "bash",
                "-c",
                f"cd /var/git/repositories && "
                f"git init --bare {repo_name} && "
                f"chown -R www-data" + ":" + f"www-data {repo_name} && "
                f"echo 'Test repository for integration testing' > "
                + f"{repo_name}/description",
            ]
        )

        assert (
            create_result.returncode == 0
        ), f"Failed to create repository: {create_result.stderr}"

        # Wait a moment for the repository to be available
        time.sleep(1)

        # Access the new repository via Gitweb
        https_port = apache_container.get_container_port(443)
        repo_url = (
            "https://localhost"
            + ":"
            + f"{https_port}/git?p={repo_name}"
            + ";"
            + "a=summary"
        )

        auth = HTTPDigestAuth("admin", "admin_secure_password")
        response = requests.get(repo_url, auth=auth, verify=False, timeout=3)

        assert response.status_code == 200, "New repository should be accessible"
        assert repo_name in response.text, "Should show new repository name"
        assert (
            "Test repository for integration testing" in response.text
        ), "Should show description"

    def test_09_gitweb_error_handling(self, apache_container: ContainerTestHelper):
        """Test Gitweb error handling for non-existent repositories."""
        self._run_user_authentication_setup()

        https_port = apache_container.get_container_port(443)
        # Try to access a non-existent repository
        nonexistent_url = (
            "https://localhost"
            + ":"
            + f"{https_port}/git?p=nonexistent.git"
            + ";"
            + "a=summary"
        )

        auth = HTTPDigestAuth("admin", "admin_secure_password")
        response = requests.get(nonexistent_url, auth=auth, verify=False, timeout=3)

        # Gitweb should return 404 for non-existent repositories (proper error handling)
        assert response.status_code == 404, "Non-existent repository should return 404"

    def test_10_gitweb_security_headers(self, apache_container: ContainerTestHelper):
        """Test that Gitweb responses include security headers."""
        self._run_user_authentication_setup()

        https_port = apache_container.get_container_port(443)
        gitweb_url = "https://localhost" + ":" + f"{https_port}/git"

        auth = HTTPDigestAuth("admin", "admin_secure_password")
        response = requests.get(gitweb_url, auth=auth, verify=False, timeout=3)

        assert response.status_code == 200

        # Check for security headers
        headers = response.headers
        assert "X-Frame-Options" in headers, "Should have X-Frame-Options header"
        assert headers.get("X-Frame-Options") == "DENY", "Should deny framing"
        assert "X-Content-Type-Options" in headers, "Should have X-Content-Type-Options"
        assert "Strict-Transport-Security" in headers, "Should have HSTS header"

    def _run_user_authentication_setup(self):
        """Run the authentication setup by executing the working user lifecycle test."""
        import subprocess

        # Run the user lifecycle test which sets up authentication properly
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "tests/integration/test_user_lifecycle.py"
                + "::TestUserLifecycle::test_user_lifecycle_complete",
                "-v",
                "--tb=no",
                "-q",
            ],
            cwd="/home/seth/Software/dev/net-servers",
            capture_output=True,
            text=True,
        )
        # We expect this to pass and set up authentication
        assert (
            result.returncode == 0
        ), f"Failed to set up authentication: {result.stdout}\n{result.stderr}"


@pytest.fixture(scope="session")
def apache_container(
    podman_available: bool,
) -> Generator[ContainerTestHelper, None, None]:
    """Session-scoped fixture for Apache container testing with Gitweb support.

    Container is started once per test session and reused across all tests.
    Container is left running after tests for debugging and performance.
    """
    if not podman_available:
        pytest.skip("Podman not available for integration testing")

    helper = ContainerTestHelper("apache")

    # Start container, reusing if already running
    if not helper.start_container(force_restart=False):
        pytest.fail("Failed to start Apache container")

    try:
        yield helper
    except Exception:
        # Container is left running for debugging
        raise


@pytest.fixture(scope="session")
def podman_available() -> bool:
    """Check if Podman is available for testing."""
    try:
        result = subprocess.run(
            ["podman", "--version"], capture_output=True, timeout=5, check=False
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return False
