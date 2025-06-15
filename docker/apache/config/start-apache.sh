#!/bin/bash
set -e

# Set default environment variables
APACHE_SERVER_NAME=${APACHE_SERVER_NAME:-"local.dev"}
APACHE_SERVER_ADMIN=${APACHE_SERVER_ADMIN:-"admin@local.dev"}
APACHE_DOCUMENT_ROOT=${APACHE_DOCUMENT_ROOT:-"/var/www/html"}
SSL_ENABLED=${SSL_ENABLED:-"false"}
SSL_CERT_FILE=${SSL_CERT_FILE:-"/data/state/certificates/local.dev/cert.pem"}
SSL_KEY_FILE=${SSL_KEY_FILE:-"/data/state/certificates/local.dev/privkey.pem"}
SSL_CHAIN_FILE=${SSL_CHAIN_FILE:-"/data/state/certificates/local.dev/fullchain.pem"}

# Ensure Apache directories exist and have correct permissions
mkdir -p ${APACHE_RUN_DIR} ${APACHE_LOCK_DIR} ${APACHE_LOG_DIR}
chown -R www-data:www-data ${APACHE_LOG_DIR} ${APACHE_RUN_DIR} ${APACHE_LOCK_DIR}
chmod 755 ${APACHE_LOG_DIR} ${APACHE_RUN_DIR} ${APACHE_LOCK_DIR}

# Setup WebDAV directories
WEBDAV_ROOT="/var/www/webdav"
WEBDAV_LOCK_DIR="/var/lock/apache2/webdav"
WEBDAV_PASSWORD_FILE="/etc/apache2/.webdav-digest"

# Create WebDAV directories
mkdir -p ${WEBDAV_ROOT} ${WEBDAV_LOCK_DIR}
chown -R www-data:www-data ${WEBDAV_ROOT} ${WEBDAV_LOCK_DIR}
chmod 755 ${WEBDAV_ROOT} ${WEBDAV_LOCK_DIR}

# Create empty WebDAV password file - the sync system will populate it
echo "Creating empty WebDAV authentication file - sync system will manage authentication"
touch "$WEBDAV_PASSWORD_FILE"
chmod 644 "$WEBDAV_PASSWORD_FILE"
chown www-data:www-data "$WEBDAV_PASSWORD_FILE"

echo "WebDAV authentication setup complete - managed by configuration sync system"

# Configure SSL if enabled and certificates exist
if [ "$SSL_ENABLED" = "true" ]; then
    echo "SSL enabled, checking for certificates..."

    if [ -f "$SSL_CERT_FILE" ] && [ -f "$SSL_KEY_FILE" ] && [ -f "$SSL_CHAIN_FILE" ]; then
        echo "SSL certificates found, enabling HTTPS..."

        # Substitute environment variables in SSL virtual host configuration
        envsubst '${APACHE_SERVER_NAME} ${APACHE_SERVER_ADMIN} ${APACHE_DOCUMENT_ROOT} ${SSL_CERT_FILE} ${SSL_KEY_FILE} ${SSL_CHAIN_FILE} ${APACHE_LOG_DIR}' \
            < /etc/apache2/sites-available/ssl-vhost.conf > /etc/apache2/sites-available/000-default-ssl.conf

        # Disable default site and enable SSL site
        a2dissite 000-default
        a2ensite 000-default-ssl
        a2enmod ssl rewrite headers

        echo "HTTPS virtual host configured, HTTP redirects enabled"
    else
        echo "Warning: SSL enabled but certificates not found. Running HTTP only."
        echo "Certificate files expected:"
        echo "  - Certificate: $SSL_CERT_FILE"
        echo "  - Private key: $SSL_KEY_FILE"
        echo "  - Chain file: $SSL_CHAIN_FILE"
    fi
else
    echo "SSL disabled, running HTTP only"
fi

# Start Apache in foreground
echo "Starting Apache HTTP Server..."
exec /usr/sbin/apache2ctl -D FOREGROUND
