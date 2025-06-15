"""Password and secrets management for net-servers."""

import base64
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import bcrypt
import yaml
from cryptography.fernet import Fernet

from .schemas import SecretsConfig, UserSecretConfig


class PasswordManager:
    """Manages user passwords and secrets."""

    def __init__(self, secrets_file_path: Path):
        """Initialize password manager with secrets file path."""
        self.secrets_file = secrets_file_path
        self._config: Optional[SecretsConfig] = None

    def _load_secrets(self) -> SecretsConfig:
        """Load secrets configuration from file."""
        if not self.secrets_file.exists():
            return SecretsConfig()

        try:
            with open(self.secrets_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return SecretsConfig(**data)
        except Exception as e:
            raise ValueError(f"Failed to load secrets from {self.secrets_file}: {e}")

    def _save_secrets(self, config: SecretsConfig) -> None:
        """Save secrets configuration to file."""
        # Ensure directory exists
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)

        # Update last_updated timestamp
        config.last_updated = datetime.now(timezone.utc).isoformat()

        with open(self.secrets_file, "w", encoding="utf-8") as f:
            yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)

        # Set restrictive permissions on secrets file
        self.secrets_file.chmod(0o600)

    def _get_config(self) -> SecretsConfig:
        """Get cached secrets configuration."""
        if self._config is None:
            self._config = self._load_secrets()
        return self._config

    def _invalidate_cache(self) -> None:
        """Invalidate cached configuration."""
        self._config = None

    def generate_password(self, length: int = 16) -> str:
        """Generate a secure random password."""
        # Use a mix of letters, digits, and safe symbols
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        return password

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return str(hashed.decode("utf-8"))

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        return bool(bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8")))

    def _get_encryption_key(self) -> bytes:
        """Get or create encryption key for password storage."""
        config = self._get_config()

        if config.encryption_key is None:
            # Generate a new encryption key
            key = Fernet.generate_key()
            config.encryption_key = base64.b64encode(key).decode("utf-8")
            self._save_secrets(config)
            self._invalidate_cache()
            return bytes(key)
        else:
            # Decode existing key
            return bytes(base64.b64decode(config.encryption_key.encode("utf-8")))

    def _encrypt_password(self, password: str) -> str:
        """Encrypt a password for secure storage."""
        key = self._get_encryption_key()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(password.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    def _decrypt_password(self, encrypted_password: str) -> str:
        """Decrypt a password from storage."""
        key = self._get_encryption_key()
        fernet = Fernet(key)
        encrypted_bytes = base64.b64decode(encrypted_password.encode("utf-8"))
        decrypted = fernet.decrypt(encrypted_bytes)
        return str(decrypted.decode("utf-8"))

    def derive_service_password(
        self, main_password: str, service: str, username: str
    ) -> str:
        """Get service password - same as main password for consistency."""
        # All services use the same password as the main password
        # This ensures users can login to WebDAV, IMAP, SMTP with the same credentials
        # Services handle authentication differently (digest, plain auth, etc.)
        # but the password the user enters is always the same
        return main_password

    def set_user_password(
        self,
        username: str,
        password: Optional[str] = None,
        webdav_password: Optional[str] = "auto",
        email_password: Optional[str] = "auto",
    ) -> str:
        """Set password for a user. Returns the password used."""
        config = self._get_config()

        # Generate password if not provided
        if password is None:
            password = self.generate_password()

        # Hash the main password for verification
        password_hash = self.hash_password(password)

        # Encrypt the main password for service derivation
        password_encrypted = self._encrypt_password(password)

        # Create timestamp
        timestamp = datetime.now(timezone.utc).isoformat()

        # Create or update user secrets
        user_secret = UserSecretConfig(
            password_hash=password_hash,
            password_encrypted=password_encrypted,
            webdav_password=webdav_password,
            email_password=email_password,
            created_at=timestamp
            if username not in config.user_secrets
            else config.user_secrets[username].created_at,
            last_changed=timestamp,
        )

        config.user_secrets[username] = user_secret
        self._save_secrets(config)
        self._invalidate_cache()

        return password

    def get_user_password_for_service(
        self, username: str, service: str
    ) -> Optional[str]:
        """Get password for a user and specific service."""
        config = self._get_config()

        if username not in config.user_secrets:  # noqa: E713
            return None

        user_secret = config.user_secrets[username]

        # Check for service-specific password override
        if service in user_secret.services:
            return user_secret.services[service]

        # Check for service-specific field (webdav_password, email_password)
        service_field = f"{service}_password"
        if hasattr(user_secret, service_field):
            value = getattr(user_secret, service_field)
            if value != "auto" and value is not None:
                return str(value)

        # For auto, derive password from main password if available
        if user_secret.password_encrypted:
            try:
                main_password = self._decrypt_password(user_secret.password_encrypted)
                return self.derive_service_password(main_password, service, username)
            except Exception:
                # If decryption fails, return None
                return None

        # Return None if no encrypted password available
        return None

    def set_service_password(self, username: str, service: str, password: str) -> None:
        """Set a service-specific password for a user."""
        config = self._get_config()

        if username not in config.user_secrets:  # noqa: E713
            raise ValueError(f"User {username} not found in secrets")

        user_secret = config.user_secrets[username]
        user_secret.services[service] = password
        user_secret.last_changed = datetime.now(timezone.utc).isoformat()

        self._save_secrets(config)
        self._invalidate_cache()

    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user password information."""
        config = self._get_config()

        if username not in config.user_secrets:  # noqa: E713
            return None

        user_secret = config.user_secrets[username]
        return {
            "username": username,
            "created_at": user_secret.created_at,
            "last_changed": user_secret.last_changed,
            "has_webdav_override": user_secret.webdav_password != "auto",
            "has_email_override": user_secret.email_password != "auto",
            "service_overrides": list(user_secret.services.keys()),
        }

    def list_users(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """List all users and their password status."""
        config = self._get_config()
        return {
            username: self.get_user_info(username) for username in config.user_secrets
        }

    def delete_user(self, username: str) -> bool:
        """Delete user secrets. Returns True if user existed."""
        config = self._get_config()

        if username not in config.user_secrets:  # noqa: E713
            return False

        del config.user_secrets[username]
        self._save_secrets(config)
        self._invalidate_cache()
        return True

    def rotate_all_passwords(self) -> Dict[str, str]:
        """Rotate passwords for all users. Returns {username: new_password}."""
        config = self._get_config()
        new_passwords = {}

        for username in config.user_secrets:
            new_password = self.set_user_password(username)
            new_passwords[username] = new_password

        return new_passwords

    def verify_user_password(self, username: str, password: str) -> bool:
        """Verify a user's password."""
        config = self._get_config()

        if username not in config.user_secrets:  # noqa: E713
            return False

        user_secret = config.user_secrets[username]
        return self.verify_password(password, user_secret.password_hash)

    def generate_service_config(
        self, username: str, service: str, main_password: str
    ) -> str:
        """Generate password for service integration (container scripts)."""
        # First check for service-specific override
        service_password = self.get_user_password_for_service(username, service)
        if service_password:
            return service_password

        # For 'auto', derive from main password with service suffix
        # This ensures consistency across container restarts
        return f"{main_password}"  # For now, just use main password

    def export_service_passwords(self, service: str) -> Dict[str, str]:
        """Export all passwords for a specific service."""
        config = self._get_config()
        passwords = {}

        for username, user_secret in config.user_secrets.items():
            # Check for service-specific password
            if service in user_secret.services:
                passwords[username] = user_secret.services[service]
            else:
                # For auto passwords, we can't export without knowing the main password
                # Used by container startup scripts with main password access
                passwords[username] = "auto"

        return passwords
