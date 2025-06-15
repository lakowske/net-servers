"""Tests for certificate CLI functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from net_servers.cli_certificates import certificates


class TestCertificatesCLI:
    """Test certificate CLI commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI runner for testing."""
        return CliRunner()

    def test_certificates_help(self, runner: CliRunner) -> None:
        """Test certificates help command."""
        result = runner.invoke(certificates, ["--help"])

        assert result.exit_code == 0
        assert "SSL/TLS certificate management commands" in result.output
        assert "provision" in result.output
        assert "list" in result.output
        assert "validate" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_provision_self_signed_success(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test successful self-signed certificate provisioning."""
        # Mock environment config
        mock_env = Mock()
        mock_env.name = "test"
        mock_env.domain = "test.local"
        mock_env.admin_email = "test@example.com"
        mock_env.certificate_mode = "self_signed"

        # Mock certificate manager
        mock_cert_manager = Mock()
        mock_cert_manager._validate_existing_certificate.return_value = False
        mock_cert_manager.provision_certificate.return_value = True
        mock_cert_manager.base_path = Path("/test/certs")

        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get_current_environment.return_value = mock_env
        mock_config_manager.get_environment_certificate_manager.return_value = (
            mock_cert_manager
        )
        mock_get_config_manager.return_value = mock_config_manager

        result = runner.invoke(
            certificates, ["provision", "--domain", "test.local", "--self-signed"]
        )

        assert result.exit_code == 0
        assert "Provisioning" in result.output
        assert "test.local" in result.output
        assert "Certificate successfully provisioned" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_provision_failure(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test failed certificate provisioning."""
        # Mock environment config
        mock_env = Mock()
        mock_env.name = "test"
        mock_env.domain = "test.local"
        mock_env.admin_email = "test@example.com"
        mock_env.certificate_mode = "self_signed"

        # Mock certificate manager
        mock_cert_manager = Mock()
        mock_cert_manager._validate_existing_certificate.return_value = False
        mock_cert_manager.provision_certificate.return_value = False
        mock_cert_manager.base_path = Path("/test/certs")

        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get_current_environment.return_value = mock_env
        mock_config_manager.get_environment_certificate_manager.return_value = (
            mock_cert_manager
        )
        mock_get_config_manager.return_value = mock_config_manager

        result = runner.invoke(
            certificates, ["provision", "--domain", "test.local", "--self-signed"]
        )

        assert result.exit_code == 1
        assert "Failed to provision certificate" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_list_certificates_success(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test successful certificate listing."""
        # Mock environment
        mock_env = Mock()
        mock_env.name = "test"
        mock_env.certificate_mode = "self_signed"

        # Mock certificate manager
        mock_cert_manager = Mock()
        mock_certificates = [
            {
                "domain": "example.com",
                "status": "valid",
                "cert_path": "/test/example.com.pem",
            },
            {
                "domain": "test.local",
                "status": "valid",
                "cert_path": "/test/test.local.pem",
            },
        ]
        mock_cert_manager.list_certificates.return_value = mock_certificates

        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get_current_environment.return_value = mock_env
        mock_config_manager.get_environment_certificate_manager.return_value = (
            mock_cert_manager
        )
        mock_get_config_manager.return_value = mock_config_manager

        result = runner.invoke(certificates, ["list"])

        assert result.exit_code == 0
        assert "example.com" in result.output
        assert "test.local" in result.output
        assert "Found 2 certificate(s)" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_list_certificates_empty(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test certificate listing with no certificates."""
        # Mock environment
        mock_env = Mock()
        mock_env.name = "test"
        mock_env.certificate_mode = "self_signed"

        # Mock certificate manager
        mock_cert_manager = Mock()
        mock_cert_manager.list_certificates.return_value = []

        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get_current_environment.return_value = mock_env
        mock_config_manager.get_environment_certificate_manager.return_value = (
            mock_cert_manager
        )
        mock_get_config_manager.return_value = mock_config_manager

        result = runner.invoke(certificates, ["list"])

        assert result.exit_code == 0
        assert "No certificates found" in result.output

    # Note: validate command tests removed due to complex mocking requirements
    # Basic certificate CLI coverage is achieved through other tests

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_manager_exception_handling(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test exception handling in certificate management."""
        mock_get_config_manager.side_effect = Exception("Permission denied")

        result = runner.invoke(
            certificates, ["provision", "--domain", "test.local", "--self-signed"]
        )

        assert result.exit_code == 1
        assert "Error:" in result.output


class TestCertificateProvisionModes:
    """Test different certificate provision modes."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI runner for testing."""
        return CliRunner()

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_provision_production_mode(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test production Let's Encrypt certificate provisioning."""
        # Mock environment config
        mock_env = Mock()
        mock_env.name = "test"
        mock_env.domain = "example.com"
        mock_env.admin_email = "admin@example.com"
        mock_env.certificate_mode = "letsencrypt"

        # Mock certificate manager
        mock_cert_manager = Mock()
        mock_cert_manager._validate_existing_certificate.return_value = False
        mock_cert_manager.provision_certificate.return_value = True
        mock_cert_manager.base_path = Path("/test/certs")

        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get_current_environment.return_value = mock_env
        mock_config_manager.get_environment_certificate_manager.return_value = (
            mock_cert_manager
        )
        mock_get_config_manager.return_value = mock_config_manager

        result = runner.invoke(
            certificates,
            [
                "provision",
                "--domain",
                "example.com",
                "--email",
                "admin@example.com",
                "--production",
            ],
        )

        assert result.exit_code == 0
        assert "example.com" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_provision_with_san(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test certificate provisioning with Subject Alternative Names."""
        # Mock environment config
        mock_env = Mock()
        mock_env.name = "test"
        mock_env.domain = "example.com"
        mock_env.admin_email = "test@example.com"
        mock_env.certificate_mode = "self_signed"

        # Mock certificate manager
        mock_cert_manager = Mock()
        mock_cert_manager._validate_existing_certificate.return_value = False
        mock_cert_manager.provision_certificate.return_value = True
        mock_cert_manager.base_path = Path("/test/certs")

        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get_current_environment.return_value = mock_env
        mock_config_manager.get_environment_certificate_manager.return_value = (
            mock_cert_manager
        )
        mock_get_config_manager.return_value = mock_config_manager

        result = runner.invoke(
            certificates,
            [
                "provision",
                "--domain",
                "example.com",
                "--san",
                "www.example.com",
                "--san",
                "mail.example.com",
                "--self-signed",
            ],
        )

        assert result.exit_code == 0

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_provision_force_flag(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test certificate provisioning with force flag."""
        # Mock environment config
        mock_env = Mock()
        mock_env.name = "test"
        mock_env.domain = "example.com"
        mock_env.admin_email = "test@example.com"
        mock_env.certificate_mode = "self_signed"

        # Mock certificate manager
        mock_cert_manager = Mock()
        mock_cert_manager._validate_existing_certificate.return_value = False
        mock_cert_manager.provision_certificate.return_value = True
        mock_cert_manager.base_path = Path("/test/certs")

        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get_current_environment.return_value = mock_env
        mock_config_manager.get_environment_certificate_manager.return_value = (
            mock_cert_manager
        )
        mock_get_config_manager.return_value = mock_config_manager

        result = runner.invoke(
            certificates,
            ["provision", "--domain", "example.com", "--self-signed", "--force"],
        )

        assert result.exit_code == 0


class TestCertificateRenewCommand:
    """Test certificate renewal CLI commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI runner for testing."""
        return CliRunner()

    @patch("net_servers.cli_certificates._get_config_manager")
    @patch("net_servers.cli_certificates.ConfigurationManager")
    def test_renew_single_certificate_success(
        self, mock_config_class: Mock, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test successful single certificate renewal."""
        # Mock certificate manager (used via cert_manager property)
        mock_cert_manager = Mock()
        mock_cert_manager.get_certificate_for_domain.return_value = Mock()
        mock_cert_manager.renew_certificate.return_value = True

        # Mock config manager from _get_config_manager
        mock_config_manager = Mock()
        mock_config_manager.cert_manager = mock_cert_manager
        mock_get_config_manager.return_value = mock_config_manager

        # Mock ConfigurationManager for global config access
        mock_config_instance = Mock()
        mock_config_instance.global_config.security.letsencrypt_email = (
            "test@example.com"
        )
        mock_config_class.return_value = mock_config_instance

        result = runner.invoke(certificates, ["renew", "--domain", "example.com"])

        assert result.exit_code == 0
        assert "Renewing certificate for example.com" in result.output
        assert "Certificate renewed for example.com" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    @patch("net_servers.cli_certificates.ConfigurationManager")
    def test_renew_single_certificate_not_needed(
        self, mock_config_class: Mock, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test certificate renewal when not needed."""
        # Mock certificate manager (used via cert_manager property)
        mock_cert_manager = Mock()
        mock_cert_manager.get_certificate_for_domain.return_value = Mock()
        mock_cert_manager.renew_certificate.return_value = False

        # Mock config manager from _get_config_manager
        mock_config_manager = Mock()
        mock_config_manager.cert_manager = mock_cert_manager
        mock_get_config_manager.return_value = mock_config_manager

        # Mock ConfigurationManager for global config access
        mock_config_instance = Mock()
        mock_config_instance.global_config.security.letsencrypt_email = (
            "test@example.com"
        )
        mock_config_class.return_value = mock_config_instance

        result = runner.invoke(certificates, ["renew", "--domain", "example.com"])

        assert result.exit_code == 0
        assert "did not need renewal" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    @patch("net_servers.cli_certificates.ConfigurationManager")
    def test_renew_all_certificates(
        self, mock_config_class: Mock, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test renewal of all certificates."""
        # Mock certificate manager (used via cert_manager property)
        mock_cert_manager = Mock()
        mock_certificates = [
            {"domain": "example.com"},
            {"domain": "test.local"},
        ]
        mock_cert_manager.list_certificates.return_value = mock_certificates
        mock_cert_manager.get_certificate_for_domain.return_value = Mock()
        mock_cert_manager.renew_certificate.side_effect = [True, False]

        # Mock config manager from _get_config_manager
        mock_config_manager = Mock()
        mock_config_manager.cert_manager = mock_cert_manager
        mock_get_config_manager.return_value = mock_config_manager

        # Mock ConfigurationManager for global config access
        mock_config_instance = Mock()
        mock_config_instance.global_config.security.letsencrypt_email = (
            "test@example.com"
        )
        mock_config_class.return_value = mock_config_instance

        result = runner.invoke(certificates, ["renew", "--all"])

        assert result.exit_code == 0
        assert "Renewing all certificates" in result.output
        assert "Renewed 1 certificates" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_renew_exception_handling(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test exception handling in certificate renewal."""
        mock_get_config_manager.side_effect = Exception("Network error")

        result = runner.invoke(certificates, ["renew", "--domain", "example.com"])

        assert result.exit_code == 1
        assert "Error:" in result.output


class TestCertificateValidateCommand:
    """Test certificate validation CLI commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI runner for testing."""
        return CliRunner()

    @patch("net_servers.cli_certificates._get_config_manager")
    @patch("net_servers.cli_certificates.ConfigurationManager")
    def test_validate_certificate_success(
        self, mock_config_class: Mock, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test successful certificate validation."""
        # Mock certificate manager (used via cert_manager property)
        mock_cert_manager = Mock()
        mock_cert_config = Mock()
        mock_cert_manager.get_certificate_for_domain.return_value = mock_cert_config
        mock_cert_manager._validate_existing_certificate.return_value = True

        # Mock config manager from _get_config_manager
        mock_config_manager = Mock()
        mock_config_manager.cert_manager = mock_cert_manager
        mock_get_config_manager.return_value = mock_config_manager

        # Mock ConfigurationManager for global config access
        mock_config_instance = Mock()
        mock_config_instance.global_config.security.letsencrypt_email = (
            "test@example.com"
        )
        mock_config_class.return_value = mock_config_instance

        result = runner.invoke(certificates, ["validate", "--domain", "example.com"])

        assert result.exit_code == 0
        assert "Certificate for example.com is valid" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    @patch("net_servers.cli_certificates.ConfigurationManager")
    def test_validate_certificate_invalid(
        self, mock_config_class: Mock, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test certificate validation failure."""
        # Mock certificate manager (used via cert_manager property)
        mock_cert_manager = Mock()
        mock_cert_config = Mock()
        mock_cert_manager.get_certificate_for_domain.return_value = mock_cert_config
        mock_cert_manager._validate_existing_certificate.return_value = False

        # Mock config manager from _get_config_manager
        mock_config_manager = Mock()
        mock_config_manager.cert_manager = mock_cert_manager
        mock_get_config_manager.return_value = mock_config_manager

        # Mock ConfigurationManager for global config access
        mock_config_instance = Mock()
        mock_config_instance.global_config.security.letsencrypt_email = (
            "test@example.com"
        )
        mock_config_class.return_value = mock_config_instance

        result = runner.invoke(certificates, ["validate", "--domain", "example.com"])

        assert result.exit_code == 1
        assert "Certificate for example.com is invalid or missing" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_validate_exception_handling(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test exception handling in certificate validation."""
        mock_get_config_manager.side_effect = Exception("File not found")

        result = runner.invoke(certificates, ["validate", "--domain", "example.com"])

        assert result.exit_code == 1
        assert "Error:" in result.output


class TestCertificateSetupCommand:
    """Test certificate setup CLI commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI runner for testing."""
        return CliRunner()

    @patch("net_servers.cli_certificates._get_config_manager")
    @patch("net_servers.cli_certificates.ConfigurationManager")
    def test_setup_certificates_success(
        self, mock_config_class: Mock, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test successful certificate setup for all domains."""
        # Mock certificate manager (used via cert_manager property)
        mock_cert_manager = Mock()
        mock_cert_manager._validate_existing_certificate.return_value = False
        mock_cert_manager.provision_certificate.return_value = True

        # Mock domains config
        mock_domain = Mock()
        mock_domain.name = "example.com"
        mock_domain.a_records = {"www": "1.2.3.4", "mail": "1.2.3.5"}

        mock_domains_config = Mock()
        mock_domains_config.domains = [mock_domain]

        # Mock config manager from _get_config_manager
        mock_config_manager = Mock()
        mock_config_manager.cert_manager = mock_cert_manager
        mock_config_manager.domains_config = mock_domains_config
        mock_get_config_manager.return_value = mock_config_manager

        # Mock ConfigurationManager for global config access
        mock_config_instance = Mock()
        mock_config_instance.global_config.security.letsencrypt_email = (
            "test@example.com"
        )
        mock_config_class.return_value = mock_config_instance

        result = runner.invoke(certificates, ["setup"])

        assert result.exit_code == 0
        assert "Setting up staging certificates" in result.output
        assert "Setup complete: 1/1 certificates ready" in result.output
        assert "All certificates are ready!" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    @patch("net_servers.cli_certificates.ConfigurationManager")
    def test_setup_no_domains_configured(
        self, mock_config_class: Mock, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test setup when no domains are configured."""
        # Mock certificate manager (used via cert_manager property)
        mock_cert_manager = Mock()

        # Mock domains config with no domains
        mock_domains_config = Mock()
        mock_domains_config.domains = []

        # Mock config manager from _get_config_manager
        mock_config_manager = Mock()
        mock_config_manager.cert_manager = mock_cert_manager
        mock_config_manager.domains_config = mock_domains_config
        mock_get_config_manager.return_value = mock_config_manager

        # Mock ConfigurationManager for global config access
        # (not used in this test but needed for consistency)
        mock_config_instance = Mock()
        mock_config_instance.global_config.security.letsencrypt_email = (
            "test@example.com"
        )
        mock_config_class.return_value = mock_config_instance

        result = runner.invoke(certificates, ["setup"])

        assert result.exit_code == 0
        assert "No domains configured" in result.output

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_setup_exception_handling(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test exception handling in certificate setup."""
        mock_get_config_manager.side_effect = Exception("Configuration error")

        result = runner.invoke(certificates, ["setup"])

        assert result.exit_code == 1
        assert "Error:" in result.output


class TestProvisionExistingCertificates:
    """Test certificate provisioning with existing certificates."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI runner for testing."""
        return CliRunner()

    @patch("net_servers.cli_certificates._get_config_manager")
    def test_provision_existing_certificate_without_force(
        self, mock_get_config_manager: Mock, runner: CliRunner
    ) -> None:
        """Test provisioning when certificate already exists without force flag."""
        # Mock environment config
        mock_env = Mock()
        mock_env.name = "test"
        mock_env.domain = "test.local"
        mock_env.admin_email = "test@example.com"
        mock_env.certificate_mode = "self_signed"

        # Mock certificate manager
        mock_cert_manager = Mock()
        mock_cert_manager._validate_existing_certificate.return_value = True  # Exists
        mock_cert_manager.base_path = Path("/test/certs")

        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get_current_environment.return_value = mock_env
        mock_config_manager.get_environment_certificate_manager.return_value = (
            mock_cert_manager
        )
        mock_get_config_manager.return_value = mock_config_manager

        result = runner.invoke(
            certificates, ["provision", "--domain", "test.local", "--self-signed"]
        )

        assert result.exit_code == 0
        assert "Certificate already exists" in result.output
        assert "Use --force to recreate" in result.output
