"""SSL/TLS certificate management with Let's Encrypt integration."""

import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class CertificateMode(Enum):
    """Certificate provisioning modes."""

    STAGING = "staging"  # Let's Encrypt staging (testing)
    PRODUCTION = "production"  # Let's Encrypt production
    SELF_SIGNED = "self_signed"  # Self-signed certificates
    EXISTING = "existing"  # Use existing certificates


@dataclass
class CertificateConfig:
    """Certificate configuration for a domain."""

    domain: str
    email: str
    mode: CertificateMode = CertificateMode.STAGING
    san_domains: List[str] = field(default_factory=list)  # Subject Alternative Names
    cert_path: str = ""
    key_path: str = ""
    fullchain_path: str = ""
    auto_renew: bool = True

    def __post_init__(self) -> None:
        """Set default paths if not provided."""
        # Note: Default paths will be overridden by CertificateManager
        # when using with ConfigurationManager environment-specific paths
        if not self.cert_path:
            base_path = f"/data/state/certificates/{self.domain}"
            self.cert_path = f"{base_path}/cert.pem"
        if not self.key_path:
            base_path = f"/data/state/certificates/{self.domain}"
            self.key_path = f"{base_path}/privkey.pem"
        if not self.fullchain_path:
            base_path = f"/data/state/certificates/{self.domain}"
            self.fullchain_path = f"{base_path}/fullchain.pem"


class CertificateManager:
    """Manages SSL/TLS certificates with Let's Encrypt integration."""

    def __init__(self, base_path: str = "/data/state/certificates"):
        """Initialize certificate manager."""
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)

        # Let's Encrypt endpoints
        self.staging_server = "https://acme-staging-v02.api.letsencrypt.org/directory"
        self.production_server = "https://acme-v02.api.letsencrypt.org/directory"

    def _ensure_certbot_installed(self) -> bool:
        """Ensure certbot is installed and available."""
        try:
            result = subprocess.run(  # nosec B607
                ["certbot", "--version"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.logger.error("Certbot not found. Please install certbot.")
            return False

    def provision_certificate(self, config: CertificateConfig) -> bool:
        """Provision a certificate based on the configuration."""
        self._ensure_certificate_directory(config)

        if config.mode == CertificateMode.SELF_SIGNED:
            return self._create_self_signed_certificate(config)
        elif config.mode in [CertificateMode.STAGING, CertificateMode.PRODUCTION]:
            if not self._ensure_certbot_installed():
                return False
            return self._provision_letsencrypt_certificate(config)
        elif config.mode == CertificateMode.EXISTING:
            return self._validate_existing_certificate(config)
        else:
            self.logger.error(f"Unknown certificate mode: {config.mode}")
            return False

    def _ensure_certificate_directory(self, config: CertificateConfig) -> None:
        """Ensure certificate directory exists."""
        cert_dir = Path(config.cert_path).parent
        cert_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Certificate directory: {cert_dir}")

    def _create_self_signed_certificate(self, config: CertificateConfig) -> bool:
        """Create self-signed certificate for development."""
        try:
            cert_dir = Path(config.cert_path).parent

            # Generate private key
            subprocess.run(  # nosec B607
                ["openssl", "genrsa", "-out", config.key_path, "2048"],
                check=True,
                capture_output=True,
            )

            # Create certificate signing request
            csr_path = cert_dir / "cert.csr"
            san_list = [config.domain] + config.san_domains
            san_config = ",".join([f"DNS:{domain}" for domain in san_list])

            subprocess.run(  # nosec B607
                [
                    "openssl",
                    "req",
                    "-new",
                    "-key",
                    config.key_path,
                    "-out",
                    str(csr_path),
                    "-subj",
                    f"/CN={config.domain}/O=Net-Servers Dev/C=US",
                    "-addext",
                    f"subjectAltName={san_config}",
                ],
                check=True,
                capture_output=True,
            )

            # Generate self-signed certificate
            subprocess.run(  # nosec B607
                [
                    "openssl",
                    "x509",
                    "-req",
                    "-in",
                    str(csr_path),
                    "-signkey",
                    config.key_path,
                    "-out",
                    config.cert_path,
                    "-days",
                    "365",
                    "-extensions",
                    "v3_req",
                    "-extfile",
                    "/dev/stdin",
                ],
                input=f"[v3_req]\nsubjectAltName={san_config}",
                text=True,
                check=True,
                capture_output=True,
            )

            # Create fullchain (same as cert for self-signed)
            subprocess.run(
                ["cp", config.cert_path, config.fullchain_path], check=True
            )  # nosec B607

            # Clean up CSR
            csr_path.unlink(missing_ok=True)

            self.logger.info(f"Self-signed certificate created for {config.domain}")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create self-signed certificate: {e}")
            return False

    def _provision_letsencrypt_certificate(self, config: CertificateConfig) -> bool:
        """Provision Let's Encrypt certificate."""
        try:
            cmd = [
                "certbot",
                "certonly",
                "--standalone",  # Use standalone mode for initial setup
                "--non-interactive",
                "--agree-tos",
                "--email",
                config.email,
                "--domains",
                config.domain,
            ]

            # Add SAN domains
            for san_domain in config.san_domains:
                cmd.extend(["--domains", san_domain])

            # Set server based on mode
            if config.mode == CertificateMode.STAGING:
                cmd.extend(["--server", self.staging_server])
                cmd.append("--test-cert")
            else:  # Production
                cmd.extend(["--server", self.production_server])

            # Set certificate output directory
            cert_dir = Path(config.cert_path).parent
            cmd.extend(["--cert-path", config.cert_path])
            cmd.extend(["--key-path", config.key_path])
            cmd.extend(["--fullchain-path", config.fullchain_path])
            cmd.extend(["--config-dir", str(cert_dir / "config")])
            cmd.extend(["--work-dir", str(cert_dir / "work")])
            cmd.extend(["--logs-dir", str(cert_dir / "logs")])

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )  # nosec B607

            if result.returncode == 0:
                mode_name = (
                    "staging"
                    if config.mode == CertificateMode.STAGING
                    else "production"
                )
                self.logger.info(
                    f"Let's Encrypt {mode_name} certificate provisioned for "
                    f"{config.domain}"
                )
                return True
            else:
                self.logger.error(f"Certbot failed: {result.stderr}")
                return False

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to provision Let's Encrypt certificate: {e}")
            return False
        except subprocess.TimeoutExpired:
            self.logger.error("Certbot command timed out")
            return False

    def _validate_existing_certificate(self, config: CertificateConfig) -> bool:
        """Validate existing certificate files."""
        required_files = [config.cert_path, config.key_path, config.fullchain_path]

        for file_path in required_files:
            if not Path(file_path).exists():
                self.logger.error(f"Required certificate file not found: {file_path}")
                return False

        # Validate certificate using openssl
        try:
            result = subprocess.run(  # nosec B607
                ["openssl", "x509", "-in", config.cert_path, "-text", "-noout"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                self.logger.info(f"Existing certificate validated for {config.domain}")
                return True
            else:
                self.logger.error(f"Certificate validation failed: {result.stderr}")
                return False

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to validate certificate: {e}")
            return False

    def renew_certificate(self, config: CertificateConfig) -> bool:
        """Renew a Let's Encrypt certificate."""
        if config.mode not in [CertificateMode.STAGING, CertificateMode.PRODUCTION]:
            self.logger.warning(f"Renewal not supported for mode: {config.mode}")
            return False

        try:
            cmd = ["certbot", "renew", "--domain", config.domain, "--non-interactive"]

            if config.mode == CertificateMode.STAGING:
                cmd.extend(["--server", self.staging_server])

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=180
            )  # nosec B607

            if result.returncode == 0:
                self.logger.info(f"Certificate renewed for {config.domain}")
                return True
            else:
                self.logger.warning(
                    f"Certificate renewal not needed or failed: {result.stderr}"
                )
                return False

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to renew certificate: {e}")
            return False

    def list_certificates(self) -> List[Dict[str, str]]:
        """List all managed certificates."""
        certificates: List[Dict[str, str]] = []

        if not self.base_path.exists():
            return certificates

        for domain_dir in self.base_path.iterdir():
            if domain_dir.is_dir():
                cert_file = domain_dir / "cert.pem"
                if cert_file.exists():
                    try:
                        # Get certificate info
                        result = subprocess.run(  # nosec B607
                            [
                                "openssl",
                                "x509",
                                "-in",
                                str(cert_file),
                                "-text",
                                "-noout",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )

                        if result.returncode == 0:
                            # Parse certificate info (basic implementation)
                            cert_info = {
                                "domain": domain_dir.name,
                                "cert_path": str(cert_file),
                                "status": "valid" if cert_file.exists() else "missing",
                            }
                            certificates.append(cert_info)

                    except subprocess.CalledProcessError:
                        certificates.append(
                            {
                                "domain": domain_dir.name,
                                "cert_path": str(cert_file),
                                "status": "invalid",
                            }
                        )

        return certificates

    def get_certificate_for_domain(
        self,
        domain: str,
        email: str,
        production_mode: bool = False,
        san_domains: Optional[List[str]] = None,
    ) -> CertificateConfig:
        """Get certificate configuration for a domain based on mode."""
        mode = (
            CertificateMode.PRODUCTION if production_mode else CertificateMode.STAGING
        )

        return CertificateConfig(
            domain=domain,
            email=email,
            mode=mode,
            san_domains=san_domains or [],
            auto_renew=True,
        )


def get_default_certificate_manager() -> CertificateManager:
    """Get default certificate manager instance."""
    return CertificateManager()
