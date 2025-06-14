"""Tests for certificate configuration management."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from net_servers.config.certificates import (
    CertificateConfig,
    CertificateManager,
    CertificateMode,
    get_default_certificate_manager,
)


class TestCertificateConfig:
    """Test certificate configuration dataclass."""

    def test_certificate_config_creation(self) -> None:
        """Test basic certificate config creation."""
        config = CertificateConfig(
            domain="test.local",
            email="test@test.local",
            mode=CertificateMode.SELF_SIGNED,
        )

        assert config.domain == "test.local"
        assert config.email == "test@test.local"
        assert config.mode == CertificateMode.SELF_SIGNED
        assert config.san_domains == []
        assert config.auto_renew is True

    def test_certificate_config_with_san_domains(self) -> None:
        """Test certificate config with SAN domains."""
        san_domains = ["www.test.local", "mail.test.local"]
        config = CertificateConfig(
            domain="test.local",
            email="test@test.local",
            mode=CertificateMode.PRODUCTION,
            san_domains=san_domains,
        )

        assert config.san_domains == san_domains
        assert config.mode == CertificateMode.PRODUCTION

    def test_certificate_config_default_paths(self) -> None:
        """Test that default paths are set correctly."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
        )

        expected_base = "/data/state/certificates/example.com"
        assert config.cert_path == f"{expected_base}/cert.pem"
        assert config.key_path == f"{expected_base}/privkey.pem"
        assert config.fullchain_path == f"{expected_base}/fullchain.pem"

    def test_certificate_config_custom_paths(self) -> None:
        """Test certificate config with custom paths."""
        config = CertificateConfig(
            domain="test.local",
            email="test@test.local",
            cert_path="/custom/cert.pem",
            key_path="/custom/key.pem",
            fullchain_path="/custom/fullchain.pem",
        )

        assert config.cert_path == "/custom/cert.pem"
        assert config.key_path == "/custom/key.pem"
        assert config.fullchain_path == "/custom/fullchain.pem"


class TestCertificateMode:
    """Test certificate mode enumeration."""

    def test_certificate_modes(self) -> None:
        """Test that all certificate modes are available."""
        assert CertificateMode.STAGING.value == "staging"
        assert CertificateMode.PRODUCTION.value == "production"
        assert CertificateMode.SELF_SIGNED.value == "self_signed"
        assert CertificateMode.EXISTING.value == "existing"


class TestCertificateManager:
    """Test certificate manager functionality."""

    @pytest.fixture
    def temp_cert_dir(self) -> str:
        """Create temporary certificate directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def cert_manager(self, temp_cert_dir: str) -> CertificateManager:
        """Create certificate manager with temporary directory."""
        return CertificateManager(temp_cert_dir)

    @pytest.fixture
    def cert_config(self, temp_cert_dir: str) -> CertificateConfig:
        """Create test certificate configuration."""
        return CertificateConfig(
            domain="test.local",
            email="test@test.local",
            mode=CertificateMode.SELF_SIGNED,
            cert_path=f"{temp_cert_dir}/test.local/cert.pem",
            key_path=f"{temp_cert_dir}/test.local/privkey.pem",
            fullchain_path=f"{temp_cert_dir}/test.local/fullchain.pem",
        )

    def test_certificate_manager_initialization(self, temp_cert_dir: str) -> None:
        """Test certificate manager initialization."""
        manager = CertificateManager(temp_cert_dir)

        assert manager.base_path == Path(temp_cert_dir)
        assert (
            manager.staging_server
            == "https://acme-staging-v02.api.letsencrypt.org/directory"
        )
        assert (
            manager.production_server
            == "https://acme-v02.api.letsencrypt.org/directory"
        )

    @patch("subprocess.run")
    def test_ensure_certbot_installed_success(
        self, mock_subprocess: Mock, cert_manager: CertificateManager
    ) -> None:
        """Test successful certbot installation check."""
        mock_subprocess.return_value.returncode = 0

        result = cert_manager._ensure_certbot_installed()

        assert result is True
        mock_subprocess.assert_called_once_with(
            ["certbot", "--version"], capture_output=True, text=True, timeout=10
        )

    @patch("subprocess.run")
    def test_ensure_certbot_installed_failure(
        self, mock_subprocess: Mock, cert_manager: CertificateManager
    ) -> None:
        """Test certbot installation check failure."""
        mock_subprocess.return_value.returncode = 1

        result = cert_manager._ensure_certbot_installed()

        assert result is False

    @patch("subprocess.run")
    def test_ensure_certbot_not_found(
        self, mock_subprocess: Mock, cert_manager: CertificateManager
    ) -> None:
        """Test certbot not found exception."""
        mock_subprocess.side_effect = FileNotFoundError()

        result = cert_manager._ensure_certbot_installed()

        assert result is False

    def test_ensure_certificate_directory(
        self, cert_manager: CertificateManager, cert_config: CertificateConfig
    ) -> None:
        """Test certificate directory creation."""
        cert_manager._ensure_certificate_directory(cert_config)

        cert_dir = Path(cert_config.cert_path).parent
        assert cert_dir.exists()
        assert cert_dir.is_dir()

    @patch("subprocess.run")
    def test_create_self_signed_certificate_success(
        self,
        mock_subprocess: Mock,
        cert_manager: CertificateManager,
        cert_config: CertificateConfig,
    ) -> None:
        """Test successful self-signed certificate creation."""
        # Mock all subprocess calls to succeed
        mock_subprocess.return_value.returncode = 0

        result = cert_manager._create_self_signed_certificate(cert_config)

        assert result is True
        # Verify all expected OpenSSL commands were called
        assert mock_subprocess.call_count == 4  # genrsa, req, x509, cp

    @patch("subprocess.run")
    def test_create_self_signed_certificate_failure(
        self,
        mock_subprocess: Mock,
        cert_manager: CertificateManager,
        cert_config: CertificateConfig,
    ) -> None:
        """Test self-signed certificate creation failure."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "openssl")

        result = cert_manager._create_self_signed_certificate(cert_config)

        assert result is False

    @patch("subprocess.run")
    def test_validate_existing_certificate_success(
        self,
        mock_subprocess: Mock,
        cert_manager: CertificateManager,
        cert_config: CertificateConfig,
    ) -> None:
        """Test successful certificate validation."""
        # Create certificate files
        cert_dir = Path(cert_config.cert_path).parent
        cert_dir.mkdir(parents=True, exist_ok=True)

        for path in [
            cert_config.cert_path,
            cert_config.key_path,
            cert_config.fullchain_path,
        ]:
            Path(path).touch()

        mock_subprocess.return_value.returncode = 0

        result = cert_manager._validate_existing_certificate(cert_config)

        assert result is True

    def test_validate_existing_certificate_missing_files(
        self, cert_manager: CertificateManager, cert_config: CertificateConfig
    ) -> None:
        """Test certificate validation with missing files."""
        result = cert_manager._validate_existing_certificate(cert_config)

        assert result is False

    @patch("subprocess.run")
    def test_validate_existing_certificate_invalid(
        self,
        mock_subprocess: Mock,
        cert_manager: CertificateManager,
        cert_config: CertificateConfig,
    ) -> None:
        """Test certificate validation with invalid certificate."""
        # Create certificate files
        cert_dir = Path(cert_config.cert_path).parent
        cert_dir.mkdir(parents=True, exist_ok=True)

        for path in [
            cert_config.cert_path,
            cert_config.key_path,
            cert_config.fullchain_path,
        ]:
            Path(path).touch()

        mock_subprocess.return_value.returncode = 1

        result = cert_manager._validate_existing_certificate(cert_config)

        assert result is False

    @patch("subprocess.run")
    def test_provision_letsencrypt_certificate_staging(
        self, mock_subprocess: Mock, cert_manager: CertificateManager
    ) -> None:
        """Test Let's Encrypt staging certificate provisioning."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            mode=CertificateMode.STAGING,
        )

        mock_subprocess.return_value.returncode = 0

        result = cert_manager._provision_letsencrypt_certificate(config)

        assert result is True
        # Verify certbot was called with staging server
        call_args = mock_subprocess.call_args[0][0]
        assert "--server" in call_args
        assert cert_manager.staging_server in call_args
        assert "--test-cert" in call_args

    @patch("subprocess.run")
    def test_provision_letsencrypt_certificate_production(
        self, mock_subprocess: Mock, cert_manager: CertificateManager
    ) -> None:
        """Test Let's Encrypt production certificate provisioning."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            mode=CertificateMode.PRODUCTION,
        )

        mock_subprocess.return_value.returncode = 0

        result = cert_manager._provision_letsencrypt_certificate(config)

        assert result is True
        # Verify certbot was called with production server
        call_args = mock_subprocess.call_args[0][0]
        assert "--server" in call_args
        assert cert_manager.production_server in call_args
        assert "--test-cert" not in call_args

    @patch("subprocess.run")
    def test_provision_letsencrypt_certificate_with_san(
        self, mock_subprocess: Mock, cert_manager: CertificateManager
    ) -> None:
        """Test Let's Encrypt certificate provisioning with SAN domains."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            mode=CertificateMode.STAGING,
            san_domains=["www.example.com", "mail.example.com"],
        )

        mock_subprocess.return_value.returncode = 0

        result = cert_manager._provision_letsencrypt_certificate(config)

        assert result is True
        # Verify SAN domains were included
        call_args = mock_subprocess.call_args[0][0]
        assert "www.example.com" in call_args
        assert "mail.example.com" in call_args

    @patch("subprocess.run")
    def test_provision_letsencrypt_certificate_failure(
        self, mock_subprocess: Mock, cert_manager: CertificateManager
    ) -> None:
        """Test Let's Encrypt certificate provisioning failure."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            mode=CertificateMode.STAGING,
        )

        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Certificate generation failed"

        result = cert_manager._provision_letsencrypt_certificate(config)

        assert result is False

    @patch("subprocess.run")
    def test_provision_letsencrypt_certificate_timeout(
        self, mock_subprocess: Mock, cert_manager: CertificateManager
    ) -> None:
        """Test Let's Encrypt certificate provisioning timeout."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            mode=CertificateMode.STAGING,
        )

        mock_subprocess.side_effect = subprocess.TimeoutExpired("certbot", 300)

        result = cert_manager._provision_letsencrypt_certificate(config)

        assert result is False

    def test_provision_certificate_self_signed(
        self, cert_manager: CertificateManager, cert_config: CertificateConfig
    ) -> None:
        """Test certificate provisioning routing for self-signed."""
        with patch.object(
            cert_manager, "_create_self_signed_certificate"
        ) as mock_create:
            mock_create.return_value = True

            result = cert_manager.provision_certificate(cert_config)

            assert result is True
            mock_create.assert_called_once_with(cert_config)

    def test_provision_certificate_letsencrypt(
        self, cert_manager: CertificateManager, temp_cert_dir: str
    ) -> None:
        """Test certificate provisioning routing for Let's Encrypt."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            mode=CertificateMode.STAGING,
            cert_path=f"{temp_cert_dir}/example.com/cert.pem",
            key_path=f"{temp_cert_dir}/example.com/privkey.pem",
            fullchain_path=f"{temp_cert_dir}/example.com/fullchain.pem",
        )

        with patch.object(cert_manager, "_ensure_certbot_installed") as mock_certbot:
            with patch.object(
                cert_manager, "_provision_letsencrypt_certificate"
            ) as mock_provision:
                mock_certbot.return_value = True
                mock_provision.return_value = True

                result = cert_manager.provision_certificate(config)

                assert result is True
                mock_certbot.assert_called_once()
                mock_provision.assert_called_once_with(config)

    def test_provision_certificate_existing(
        self, cert_manager: CertificateManager, temp_cert_dir: str
    ) -> None:
        """Test certificate provisioning routing for existing certificates."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            mode=CertificateMode.EXISTING,
            cert_path=f"{temp_cert_dir}/example.com/cert.pem",
            key_path=f"{temp_cert_dir}/example.com/privkey.pem",
            fullchain_path=f"{temp_cert_dir}/example.com/fullchain.pem",
        )

        with patch.object(
            cert_manager, "_validate_existing_certificate"
        ) as mock_validate:
            mock_validate.return_value = True

            result = cert_manager.provision_certificate(config)

            assert result is True
            mock_validate.assert_called_once_with(config)

    def test_provision_certificate_unknown_mode(
        self, cert_manager: CertificateManager, temp_cert_dir: str
    ) -> None:
        """Test certificate provisioning with unknown mode."""
        # Create a mock mode that doesn't exist
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            cert_path=f"{temp_cert_dir}/example.com/cert.pem",
            key_path=f"{temp_cert_dir}/example.com/privkey.pem",
            fullchain_path=f"{temp_cert_dir}/example.com/fullchain.pem",
        )
        config.mode = "unknown_mode"  # Force invalid mode

        result = cert_manager.provision_certificate(config)

        assert result is False

    @patch("subprocess.run")
    def test_renew_certificate_success(
        self, mock_subprocess: Mock, cert_manager: CertificateManager
    ) -> None:
        """Test successful certificate renewal."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            mode=CertificateMode.PRODUCTION,
        )

        mock_subprocess.return_value.returncode = 0

        result = cert_manager.renew_certificate(config)

        assert result is True

    @patch("subprocess.run")
    def test_renew_certificate_not_needed(
        self, mock_subprocess: Mock, cert_manager: CertificateManager
    ) -> None:
        """Test certificate renewal when not needed."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            mode=CertificateMode.PRODUCTION,
        )

        mock_subprocess.return_value.returncode = 1

        result = cert_manager.renew_certificate(config)

        assert result is False

    def test_renew_certificate_unsupported_mode(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test certificate renewal with unsupported mode."""
        config = CertificateConfig(
            domain="example.com",
            email="test@example.com",
            mode=CertificateMode.SELF_SIGNED,
        )

        result = cert_manager.renew_certificate(config)

        assert result is False

    def test_list_certificates_empty(self, cert_manager: CertificateManager) -> None:
        """Test listing certificates when none exist."""
        result = cert_manager.list_certificates()

        assert result == []

    def test_list_certificates_with_certs(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test listing certificates when some exist."""
        # Create mock certificate directories
        cert_dir1 = cert_manager.base_path / "example.com"
        cert_dir1.mkdir(parents=True)
        (cert_dir1 / "cert.pem").touch()

        cert_dir2 = cert_manager.base_path / "test.local"
        cert_dir2.mkdir(parents=True)
        (cert_dir2 / "cert.pem").touch()

        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.return_value.returncode = 0

            result = cert_manager.list_certificates()

            assert len(result) == 2
            domains = [cert["domain"] for cert in result]
            assert "example.com" in domains
            assert "test.local" in domains

    def test_list_certificates_with_invalid_cert(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test listing certificates with invalid certificate."""
        # Create mock certificate directory with invalid cert
        cert_dir = cert_manager.base_path / "invalid.com"
        cert_dir.mkdir(parents=True)
        (cert_dir / "cert.pem").touch()

        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.side_effect = subprocess.CalledProcessError(1, "openssl")

            result = cert_manager.list_certificates()

            assert len(result) == 1
            assert result[0]["domain"] == "invalid.com"
            assert result[0]["status"] == "invalid"

    def test_get_certificate_for_domain_staging(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test getting certificate configuration for domain in staging mode."""
        config = cert_manager.get_certificate_for_domain(
            "example.com", "test@example.com", production_mode=False
        )

        assert config.domain == "example.com"
        assert config.email == "test@example.com"
        assert config.mode == CertificateMode.STAGING
        assert config.auto_renew is True

    def test_get_certificate_for_domain_production(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test getting certificate configuration for domain in production mode."""
        config = cert_manager.get_certificate_for_domain(
            "example.com", "test@example.com", production_mode=True
        )

        assert config.domain == "example.com"
        assert config.email == "test@example.com"
        assert config.mode == CertificateMode.PRODUCTION

    def test_get_certificate_for_domain_with_san(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test getting certificate configuration with SAN domains."""
        san_domains = ["www.example.com", "mail.example.com"]
        config = cert_manager.get_certificate_for_domain(
            "example.com", "test@example.com", san_domains=san_domains
        )

        assert config.san_domains == san_domains


class TestGetDefaultCertificateManager:
    """Test default certificate manager factory function."""

    def test_get_default_certificate_manager(self) -> None:
        """Test getting default certificate manager instance."""
        manager = get_default_certificate_manager()

        assert isinstance(manager, CertificateManager)
        assert manager.base_path == Path("/data/state/certificates")
