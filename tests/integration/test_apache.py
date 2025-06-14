"""Integration tests for Apache container."""

import time

import requests

from .conftest import ContainerTestHelper


class TestApacheContainer:
    """Test Apache container functionality in logical order."""

    def test_01_container_starts_successfully(
        self, apache_container: ContainerTestHelper
    ):
        """Test that Apache container starts and is running."""
        assert apache_container.is_container_ready()

    def test_02_apache_serves_pages(self, apache_container: ContainerTestHelper):
        """Test Apache serves HTTP requests (service running and accessible)."""
        # Test HTTPS first since container enables SSL by default
        https_port = apache_container.get_container_port(443)
        https_url = "https://localhost:" + str(https_port)

        # Make HTTPS request with retry logic and SSL verification disabled
        response = None
        for attempt in range(5):
            try:
                response = requests.get(https_url, timeout=10, verify=False)
                if response.status_code == 200:
                    break
            except requests.RequestException:
                if attempt == 4:  # Last attempt
                    raise
                time.sleep(2)

        assert response.status_code == 200
        # Check for content that should be in our custom index.html
        content = response.text.lower()
        assert "apache" in content or "server" in content or "welcome" in content

        # Test HTTP redirect to HTTPS
        http_port = apache_container.get_container_port(80)
        http_url = "http://localhost:" + str(http_port)

        # Test that HTTP redirects (don't follow to avoid SSL issues)
        response = requests.get(http_url, timeout=10, allow_redirects=False)
        assert response.status_code == 301  # Should redirect to HTTPS

    def test_03_apache_error_handling(self, apache_container: ContainerTestHelper):
        """Test Apache error handling for non-existent pages."""
        # Use HTTPS since SSL is enabled
        port = apache_container.get_container_port(443)
        url = "https://localhost:" + str(port) + "/nonexistent-page"

        # Create a new session to avoid connection reuse issues
        session = requests.Session()
        session.verify = False
        response = session.get(url, timeout=10)
        session.close()

        assert response.status_code == 404

    def test_04_apache_configuration_loaded(
        self, apache_container: ContainerTestHelper
    ):
        """Test that Apache configuration modules are properly loaded."""
        result = apache_container.exec_command(["apache2ctl", "-M"])
        assert result.returncode == 0

        # Check for modules we enabled in configuration
        modules = result.stdout.lower()
        assert "rewrite_module" in modules
        assert "headers_module" in modules
        assert "deflate_module" in modules

    def test_05_apache_logs_accessible(self, apache_container: ContainerTestHelper):
        """Test that Apache logs are accessible and being written."""
        result = apache_container.exec_command(["ls", "-la", "/var/log/apache2/"])
        assert result.returncode == 0
        log_output = result.stdout
        assert "access.log" in log_output or "other_vhosts_access.log" in log_output
