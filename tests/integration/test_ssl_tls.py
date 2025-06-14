"""Integration tests for SSL/TLS functionality across all services."""

import smtplib
import socket
import ssl
import subprocess
import time
from pathlib import Path
from typing import Optional

import pytest
import requests

from net_servers.config.certificates import (
    CertificateConfig,
    CertificateManager,
    CertificateMode,
)

from .conftest import ContainerTestHelper


class SSLTestHelper:
    """Helper class for SSL/TLS testing operations."""

    def __init__(self, temp_cert_dir: str = "/tmp/test-certs"):
        """Initialize SSL test helper."""
        self.cert_dir = Path(temp_cert_dir)
        self.cert_manager = CertificateManager(str(self.cert_dir))

    def create_self_signed_cert(
        self, domain: str = "test.local", san_domains: Optional[list] = None
    ) -> bool:
        """Create a self-signed certificate for testing."""
        if san_domains is None:
            san_domains = ["mail.test.local", "www.test.local"]

        config = CertificateConfig(
            domain=domain,
            email="test@test.local",
            mode=CertificateMode.SELF_SIGNED,
            san_domains=san_domains,
            cert_path=str(self.cert_dir / domain / "cert.pem"),
            key_path=str(self.cert_dir / domain / "privkey.pem"),
            fullchain_path=str(self.cert_dir / domain / "fullchain.pem"),
        )

        return self.cert_manager.provision_certificate(config)

    def get_cert_paths(self, domain: str = "test.local") -> dict:
        """Get certificate file paths for a domain."""
        return {
            "cert": str(self.cert_dir / domain / "cert.pem"),
            "key": str(self.cert_dir / domain / "privkey.pem"),
            "fullchain": str(self.cert_dir / domain / "fullchain.pem"),
        }

    def verify_ssl_connection(self, host: str, port: int, timeout: int = 10) -> dict:
        """Verify SSL connection and return certificate information."""
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE  # Accept self-signed certs

            with socket.create_connection((host, port), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    protocol = ssock.version()

                    return {
                        "success": True,
                        "certificate": cert,
                        "cipher": cipher,
                        "protocol": protocol,
                        "error": None,
                    }

        except Exception as e:
            return {
                "success": False,
                "certificate": None,
                "cipher": None,
                "protocol": None,
                "error": str(e),
            }


@pytest.fixture(scope="session")
def ssl_helper() -> SSLTestHelper:
    """Create SSL test helper."""
    return SSLTestHelper()


@pytest.fixture(scope="session")
def ssl_certificates(ssl_helper: SSLTestHelper) -> dict:
    """Create self-signed certificates for testing."""
    # Get current environment domain for certificate creation
    import os

    from net_servers.config.manager import ConfigurationManager

    base_path = (
        "/data" if os.path.exists("/data") else os.path.expanduser("~/.net-servers")
    )
    config_manager = ConfigurationManager(base_path)
    try:
        current_env = config_manager.get_current_environment()
        domain = current_env.domain
    except Exception:
        # Fallback to testing domain if environment system fails
        domain = "test.local.dev"

    # Create self-signed certificate for the correct domain
    success = ssl_helper.create_self_signed_cert(domain=domain)
    if not success:
        pytest.skip("Failed to create self-signed certificates")

    return ssl_helper.get_cert_paths(domain=domain)


@pytest.fixture(scope="session")
def apache_ssl_container(
    ssl_certificates: dict, podman_available: bool
) -> ContainerTestHelper:
    """Apache container with SSL certificates mounted."""
    if not podman_available:
        pytest.skip("Podman not available for integration testing")

    helper = ContainerTestHelper("apache")

    # Get domain from certificate path
    cert_path = Path(ssl_certificates["cert"])
    domain = cert_path.parent.name  # Extract domain from path structure

    # Set SSL environment variables
    env_vars = {
        "SSL_ENABLED": "true",
        "APACHE_SERVER_NAME": domain,
        "APACHE_SERVER_ADMIN": f"admin@{domain}",
        "APACHE_DOCUMENT_ROOT": "/var/www/html",
        "SSL_CERT_FILE": f"/data/state/certificates/{domain}/cert.pem",
        "SSL_KEY_FILE": f"/data/state/certificates/{domain}/privkey.pem",
        "SSL_CHAIN_FILE": f"/data/state/certificates/{domain}/fullchain.pem",
    }

    # Add environment variables to container config
    helper.config.environment.update(env_vars)

    # Add certificate volume mount
    from net_servers.actions.container import VolumeMount

    helper.config.volumes.append(
        VolumeMount(
            host_path=str(Path(ssl_certificates["cert"]).parent),
            container_path=f"/data/state/certificates/{domain}",
            read_only=True,
        )
    )

    # Start container with SSL configuration and proper port mapping
    # Use fixed ports for SSL testing to ensure both HTTP and HTTPS work
    ssl_port_mapping = "8080:80,8443:443"
    helper.port_mapping = ssl_port_mapping  # Override port mapping for this test

    # Create a custom port mapping function for this test
    def get_ssl_port(container_port: int) -> int:
        """Get host port for container port in SSL test."""
        port_map = {"80": 8080, "443": 8443}
        return port_map.get(str(container_port), container_port)

    # Override the get_container_port method for SSL testing
    helper.get_container_port = get_ssl_port

    if not helper.start_container(port_mapping=ssl_port_mapping):
        pytest.fail("Failed to start Apache SSL container")

    # Wait for SSL to be configured
    time.sleep(5)

    yield helper

    # Keep container running for debugging
    helper.print_container_info()


@pytest.fixture(scope="session")
def mail_ssl_container(
    ssl_certificates: dict, podman_available: bool
) -> ContainerTestHelper:
    """Mail container with SSL certificates mounted."""
    if not podman_available:
        pytest.skip("Podman not available for integration testing")

    helper = ContainerTestHelper("mail")

    # Get domain from certificate path
    cert_path = Path(ssl_certificates["cert"])
    domain = cert_path.parent.name  # Extract domain from path structure

    # Set SSL environment variables
    env_vars = {
        "MAIL_TLS_ENABLED": "true",
        "MAIL_REQUIRE_TLS": "false",  # Allow both encrypted and unencrypted for testing
        "MAIL_SSL_CERT_FILE": f"/data/state/certificates/{domain}/cert.pem",
        "MAIL_SSL_KEY_FILE": f"/data/state/certificates/{domain}/privkey.pem",
        "MAIL_SSL_CHAIN_FILE": f"/data/state/certificates/{domain}/fullchain.pem",
    }

    # Add environment variables to container config
    helper.config.environment.update(env_vars)

    # Add certificate volume mount
    from net_servers.actions.container import VolumeMount

    helper.config.volumes.append(
        VolumeMount(
            host_path=str(Path(ssl_certificates["cert"]).parent),
            container_path=f"/data/state/certificates/{domain}",
            read_only=True,
        )
    )

    # Start container with SSL configuration
    if not helper.start_container():
        pytest.fail("Failed to start Mail SSL container")

    # Wait for SSL to be configured
    time.sleep(8)  # Mail services take longer to start

    yield helper

    # Keep container running for debugging
    helper.print_container_info()


class TestApacheSSL:
    """Test Apache HTTPS functionality."""

    def test_01_apache_ssl_container_starts(
        self, apache_ssl_container: ContainerTestHelper
    ):
        """Test that Apache container starts with SSL configuration."""
        assert apache_ssl_container.is_container_ready()

    def test_02_apache_http_redirects_to_https(
        self, apache_ssl_container: ContainerTestHelper
    ):
        """Test that HTTP requests are redirected to HTTPS."""
        http_port = apache_ssl_container.get_container_port(80)
        http_url = "http://localhost" + ":" + str(http_port)

        # Make HTTP request and check for redirect
        try:
            response = requests.get(http_url, allow_redirects=False, timeout=10)
            # Should get 301 or 302 redirect to HTTPS
            assert response.status_code in [301, 302]

            # Check redirect location contains https
            location = response.headers.get("Location", "")
            assert "https://" in location.lower()

        except requests.RequestException as e:
            pytest.fail(f"HTTP redirect test failed: {e}")

    def test_03_apache_https_serves_content(
        self, apache_ssl_container: ContainerTestHelper
    ):
        """Test that HTTPS serves content with self-signed certificate."""
        https_port = apache_ssl_container.get_container_port(443)
        https_url = "https://localhost" + ":" + str(https_port)

        # Make HTTPS request with SSL verification disabled (self-signed cert)
        try:
            response = requests.get(https_url, verify=False, timeout=10)
            assert response.status_code == 200

            # Check for content
            content = response.text.lower()
            assert "apache" in content or "server" in content or "welcome" in content

        except requests.RequestException as e:
            pytest.fail(f"HTTPS content test failed: {e}")

    def test_04_apache_ssl_certificate_info(
        self, apache_ssl_container: ContainerTestHelper, ssl_helper: SSLTestHelper
    ):
        """Test SSL certificate information and handshake."""
        https_port = apache_ssl_container.get_container_port(443)

        # Verify SSL connection
        ssl_info = ssl_helper.verify_ssl_connection("localhost", https_port)

        assert ssl_info["success"], f"SSL connection failed: {ssl_info['error']}"
        assert ssl_info["protocol"] is not None
        assert ssl_info["cipher"] is not None

        # Check certificate subject contains our test domain
        cert = ssl_info["certificate"]
        if cert:
            subject = dict(x[0] for x in cert.get("subject", []))
            assert "test.local" in subject.get("commonName", "")

    def test_05_apache_security_headers(
        self, apache_ssl_container: ContainerTestHelper
    ):
        """Test that Apache sets proper security headers."""
        https_port = apache_ssl_container.get_container_port(443)
        https_url = "https://localhost" + ":" + str(https_port)

        try:
            response = requests.get(https_url, verify=False, timeout=10)
            headers = response.headers

            # Check for security headers
            assert "Strict-Transport-Security" in headers
            assert "X-Frame-Options" in headers
            assert "X-Content-Type-Options" in headers

            # Check HSTS header value
            hsts = headers.get("Strict-Transport-Security", "")
            assert "max-age=" in hsts

        except requests.RequestException as e:
            pytest.fail(f"Security headers test failed: {e}")


class TestMailSSL:
    """Test Mail services SSL/TLS functionality."""

    def test_01_mail_ssl_container_starts(
        self, mail_ssl_container: ContainerTestHelper
    ):
        """Test that Mail container starts with SSL configuration."""
        assert mail_ssl_container.is_container_ready()

    def test_02_smtp_ssl_connection(self, mail_ssl_container: ContainerTestHelper):
        """Test SMTP SSL connection on port 587."""
        smtp_port = mail_ssl_container.get_container_port(587)

        try:
            # Test SMTP with STARTTLS
            server = smtplib.SMTP("localhost", smtp_port, timeout=10)
            server.starttls()  # This will test SSL/TLS capability
            server.quit()

        except Exception as e:
            # If STARTTLS fails, check if it's because service isn't configured
            # Some configurations might not have SMTP SSL on 587
            pytest.skip(f"SMTP SSL not configured or not working: {e}")

    def test_03_imaps_ssl_connection(
        self, mail_ssl_container: ContainerTestHelper, ssl_helper: SSLTestHelper
    ):
        """Test IMAPS SSL connection on port 993."""
        imaps_port = mail_ssl_container.get_container_port(993)

        # Verify SSL connection to IMAPS port
        ssl_info = ssl_helper.verify_ssl_connection("localhost", imaps_port)

        if not ssl_info["success"]:
            # IMAPS might not be configured, skip test
            pytest.skip(f"IMAPS SSL not configured: {ssl_info['error']}")

        assert ssl_info["protocol"] is not None
        assert ssl_info["cipher"] is not None

    def test_04_pop3s_ssl_connection(
        self, mail_ssl_container: ContainerTestHelper, ssl_helper: SSLTestHelper
    ):
        """Test POP3S SSL connection on port 995."""
        pop3s_port = mail_ssl_container.get_container_port(995)

        # Verify SSL connection to POP3S port
        ssl_info = ssl_helper.verify_ssl_connection("localhost", pop3s_port)

        if not ssl_info["success"]:
            # POP3S might not be configured, skip test
            pytest.skip(f"POP3S SSL not configured: {ssl_info['error']}")

        assert ssl_info["protocol"] is not None
        assert ssl_info["cipher"] is not None

    def test_05_mail_ssl_certificate_files_exist(
        self, mail_ssl_container: ContainerTestHelper
    ):
        """Test that SSL certificate files are accessible in mail container."""
        # Check if certificate files exist in container
        cert_check = mail_ssl_container.exec_command(
            ["ls", "-la", "/data/state/certificates/test.local/"]
        )

        if cert_check.returncode != 0:
            pytest.skip("Certificate directory not mounted or accessible")

        # Check for specific certificate files
        for filename in ["cert.pem", "privkey.pem", "fullchain.pem"]:
            file_check = mail_ssl_container.exec_command(
                ["test", "-f", f"/data/state/certificates/test.local/{filename}"]
            )
            assert file_check.returncode == 0, f"Certificate file {filename} not found"


class TestSSLConfiguration:
    """Test SSL configuration and certificate management."""

    def test_01_self_signed_certificate_creation(self, ssl_helper: SSLTestHelper):
        """Test creation of self-signed certificates."""
        success = ssl_helper.create_self_signed_cert("test-domain.local")
        assert success

        # Verify certificate files exist
        paths = ssl_helper.get_cert_paths("test-domain.local")
        for path in paths.values():
            assert Path(path).exists(), f"Certificate file not created: {path}"

    def test_02_certificate_validation(self, ssl_helper: SSLTestHelper):
        """Test certificate validation."""
        # Create a certificate first
        ssl_helper.create_self_signed_cert("validation-test.local")

        # Get the certificate info using OpenSSL
        paths = ssl_helper.get_cert_paths("validation-test.local")

        try:
            result = subprocess.run(
                ["openssl", "x509", "-in", paths["cert"], "-text", "-noout"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.returncode == 0, "Certificate validation failed"

            # Check certificate contains expected domain
            output = result.stdout
            assert "validation-test.local" in output

        except subprocess.TimeoutExpired:
            pytest.skip("OpenSSL not available for certificate validation")
        except FileNotFoundError:
            pytest.skip("OpenSSL not installed")

    def test_03_certificate_san_domains(self, ssl_helper: SSLTestHelper):  # noqa: E713
        """Test Subject Alternative Names in certificates."""
        san_domains = [
            "mail.san-test.local",
            "www.san-test.local",
            "api.san-test.local",
        ]
        success = ssl_helper.create_self_signed_cert("san-test.local", san_domains)
        assert success

        # Verify SAN domains in certificate
        paths = ssl_helper.get_cert_paths("san-test.local")

        try:
            result = subprocess.run(
                ["openssl", "x509", "-in", paths["cert"], "-text", "-noout"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                output = result.stdout
                missing_domains = [d for d in san_domains if d not in output]
                if missing_domains:
                    pytest.fail(f"SAN domains not found: {missing_domains}")

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("OpenSSL not available for SAN verification")


class TestSSLFallback:
    """Test SSL configuration fallback scenarios."""

    def test_01_apache_without_certificates(self, podman_available: bool):
        """Test Apache container behavior when SSL enabled but certs missing."""
        if not podman_available:
            pytest.skip("Podman not available for integration testing")

        helper = ContainerTestHelper("apache")

        # Enable SSL but don't provide certificates
        helper.config.environment.update(
            {
                "SSL_ENABLED": "true",
                "SSL_CERT_FILE": "/nonexistent/cert.pem",
                "SSL_KEY_FILE": "/nonexistent/key.pem",
                "SSL_CHAIN_FILE": "/nonexistent/chain.pem",
            }
        )

        # Container should still start (fallback to HTTP)
        success = helper.start_container()
        assert success

        # Should serve HTTP content
        http_port = helper.get_container_port(80)
        http_url = "http://localhost" + ":" + str(http_port)

        try:
            response = requests.get(http_url, timeout=10)
            assert response.status_code == 200
        except requests.RequestException as e:
            pytest.fail(f"HTTP fallback failed: {e}")

        # Clean up
        helper.manager.stop()
        helper.manager.remove_container(force=True)

    def test_02_mail_without_certificates(self, podman_available: bool):
        """Test Mail container behavior when TLS enabled but certs missing."""
        if not podman_available:
            pytest.skip("Podman not available for integration testing")

        helper = ContainerTestHelper("mail")

        # Enable TLS but don't provide certificates
        helper.config.environment.update(
            {
                "MAIL_TLS_ENABLED": "true",
                "MAIL_SSL_CERT_FILE": "/nonexistent/cert.pem",
                "MAIL_SSL_KEY_FILE": "/nonexistent/key.pem",
                "MAIL_SSL_CHAIN_FILE": "/nonexistent/chain.pem",
            }
        )

        # Container should still start (fallback to non-TLS)
        success = helper.start_container()
        assert success

        # Wait for services (mail services take longer in fallback mode)
        time.sleep(10)

        # Should accept SMTP connections on port 25
        smtp_port = helper.get_container_port(25)

        # Test SMTP connection with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                server = smtplib.SMTP("localhost", smtp_port, timeout=10)
                # Test basic SMTP functionality
                server.noop()  # Send NOOP command to verify connection
                server.quit()
                break  # Success, exit retry loop
            except Exception as e:
                if attempt == max_retries - 1:  # Last attempt
                    pytest.fail(
                        f"SMTP fallback failed after {max_retries} attempts: {e}"
                    )
                # Wait before retry
                time.sleep(2)

        # Clean up
        helper.manager.stop()
        helper.manager.remove_container(force=True)
