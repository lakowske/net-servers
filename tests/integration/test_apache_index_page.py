"""Integration tests for Apache index page content and service links.

Tests verify that the index page properly displays available services including Gitweb.
"""

from typing import Generator

import pytest
import requests

from .conftest import ContainerTestHelper


class TestApacheIndexPage:
    """Test Apache index page content and service links."""

    def test_01_index_page_accessible(self, apache_container: ContainerTestHelper):
        """Test that the Apache index page is accessible via HTTPS."""
        https_port = apache_container.get_container_port(443)
        index_url = "https://localhost" + ":" + f"{https_port}/"

        response = requests.get(
            index_url, verify=False, timeout=3  # Self-signed certificate
        )

        assert response.status_code == 200, "Index page should be accessible"
        assert (
            "Net Servers Apache Container" in response.text
        ), "Should show main heading"

    def test_02_index_page_shows_available_services(
        self, apache_container: ContainerTestHelper
    ):
        """Test that the index page shows both WebDAV and Gitweb services."""
        https_port = apache_container.get_container_port(443)
        index_url = "https://localhost" + ":" + f"{https_port}/"

        response = requests.get(index_url, verify=False, timeout=3)

        assert response.status_code == 200

        # Check for Available Services section
        assert "Available Services:" in response.text, "Should show services section"

        # Check for WebDAV service
        assert "WebDAV:" in response.text, "Should show WebDAV service"
        assert (
            "https://localhost:8543/webdav/" in response.text
        ), "Should have WebDAV link"

        # Check for Gitweb service
        assert "Gitweb:" in response.text, "Should show Gitweb service"
        assert "https://localhost:8543/git" in response.text, "Should have Gitweb link"

    def test_03_index_page_shows_webdav_details(
        self, apache_container: ContainerTestHelper
    ):
        """Test that the index page shows WebDAV service details."""
        https_port = apache_container.get_container_port(443)
        index_url = "https://localhost" + ":" + f"{https_port}/"

        response = requests.get(index_url, verify=False, timeout=3)

        assert response.status_code == 200

        # Check for WebDAV section
        assert "WebDAV File Storage (HTTPS Required)" in response.text
        assert "secure WebDAV support for file upload/download" in response.text
        assert "Browse files via HTTPS" in response.text
        assert "Map network drive" in response.text
        assert "WebDAV requires HTTPS and user authentication" in response.text

    def test_04_index_page_shows_gitweb_details(
        self, apache_container: ContainerTestHelper
    ):
        """Test that the index page shows Gitweb service details."""
        https_port = apache_container.get_container_port(443)
        index_url = "https://localhost" + ":" + f"{https_port}/"

        response = requests.get(index_url, verify=False, timeout=3)

        assert response.status_code == 200

        # Check for Gitweb section
        assert "Gitweb Repository Browser (HTTPS Required)" in response.text
        assert "browsing Git repositories through a web interface" in response.text
        assert "Browse Git repositories via HTTPS" in response.text
        assert (
            "Repository listing, commit history, file browsing, and diffs"
            in response.text
        )
        assert "/var/git/repositories/" in response.text
        assert "sample.git" in response.text
        assert "Gitweb requires HTTPS and user authentication" in response.text
        assert "Uses same authentication as WebDAV" in response.text

    def test_05_index_page_shows_sample_repository_link(
        self, apache_container: ContainerTestHelper
    ):
        """Test that the index page includes a direct link to the sample repository."""
        https_port = apache_container.get_container_port(443)
        index_url = "https://localhost" + ":" + f"{https_port}/"

        response = requests.get(index_url, verify=False, timeout=3)

        assert response.status_code == 200

        # Check for direct sample repository link
        sample_repo_link = "https://localhost:8543/git?p=sample.git;a=summary"
        assert (
            sample_repo_link in response.text
        ), "Should have direct link to sample repository"

    def test_06_index_page_shows_correct_port_mappings(
        self, apache_container: ContainerTestHelper
    ):
        """Test that the index page shows correct port mappings."""
        https_port = apache_container.get_container_port(443)
        index_url = "https://localhost" + ":" + f"{https_port}/"

        response = requests.get(index_url, verify=False, timeout=3)

        assert response.status_code == 200

        # Check for correct port mappings
        assert (
            "Port mapping: 8180 -> 80, 8543 -> 443" in response.text
        ), "Should show correct port mappings"

    def test_07_http_redirects_to_https(self, apache_container: ContainerTestHelper):
        """Test that HTTP access redirects to HTTPS."""
        http_port = apache_container.get_container_port(80)
        http_url = "http://localhost" + ":" + f"{http_port}/"

        response = requests.get(http_url, allow_redirects=False, timeout=3)

        assert response.status_code == 301, "HTTP should redirect to HTTPS"
        assert "https://" in response.headers.get(
            "Location", ""
        ), "Should redirect to HTTPS URL"

    def test_08_index_page_styling_and_branding(
        self, apache_container: ContainerTestHelper
    ):
        """Test that the index page has proper styling and Net Servers branding."""
        https_port = apache_container.get_container_port(443)
        index_url = "https://localhost" + ":" + f"{https_port}/"

        response = requests.get(index_url, verify=False, timeout=3)

        assert response.status_code == 200

        # Check for styling and branding elements
        assert (
            "Net Servers Apache Container" in response.text
        ), "Should show Net Servers branding"
        assert "Apache HTTP Server" in response.text, "Should show server type"
        assert "Debian 12 Slim" in response.text, "Should show base image"
        assert "Development Server" in response.text, "Should show container type"
        assert "Running Successfully!" in response.text, "Should show status"

        # Check for CSS styling
        assert (
            "font-family: Arial, sans-serif" in response.text
        ), "Should have CSS styling"
        assert "background: #f4f4f4" in response.text, "Should have background styling"


@pytest.fixture(scope="session")
def apache_container(
    podman_available: bool,
) -> Generator[ContainerTestHelper, None, None]:
    """Session-scoped fixture for Apache container testing.

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
    import subprocess

    try:
        result = subprocess.run(
            ["podman", "--version"], capture_output=True, timeout=5, check=False
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return False
