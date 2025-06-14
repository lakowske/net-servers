#!/bin/bash

# Start script for mail server container
set -e

echo "Starting mail server container..."

# Set default SSL environment variables
MAIL_TLS_ENABLED=${MAIL_TLS_ENABLED:-"false"}
MAIL_REQUIRE_TLS=${MAIL_REQUIRE_TLS:-"false"}
MAIL_SSL_CERT_FILE=${MAIL_SSL_CERT_FILE:-"/data/state/certificates/local.dev/cert.pem"}
MAIL_SSL_KEY_FILE=${MAIL_SSL_KEY_FILE:-"/data/state/certificates/local.dev/privkey.pem"}
MAIL_SSL_CHAIN_FILE=${MAIL_SSL_CHAIN_FILE:-"/data/state/certificates/local.dev/fullchain.pem"}

# Create required directories
mkdir -p /var/log/supervisor
mkdir -p /var/log/postfix
mkdir -p /var/log/dovecot
mkdir -p /var/mail/vhosts
mkdir -p /var/spool/postfix/private

# Set proper permissions
chown -R vmail:vmail /var/mail/vhosts
chown -R postfix:postfix /var/log/postfix
chown -R dovecot:dovecot /var/log/dovecot
chmod 755 /var/mail/vhosts

# Create a test user for development
echo "Creating test users file..."
mkdir -p /etc/dovecot
echo 'test@local:{PLAIN}password' > /etc/dovecot/users
echo 'user@local:{PLAIN}password' >> /etc/dovecot/users
chown root:dovecot /etc/dovecot/users
chmod 640 /etc/dovecot/users

# Create virtual domain files for Postfix
echo "local    OK" > /etc/postfix/virtual_domains
echo "test@local test@local/" > /etc/postfix/virtual_mailboxes
echo "user@local user@local/" >> /etc/postfix/virtual_mailboxes
echo "admin@local test@local" > /etc/postfix/virtual_aliases

# Set permissions for Postfix virtual files
chown root:postfix /etc/postfix/virtual_*
chmod 644 /etc/postfix/virtual_*

# Update postfix maps
postmap /etc/postfix/virtual_domains 2>/dev/null || true
postmap /etc/postfix/virtual_mailboxes 2>/dev/null || true
postmap /etc/postfix/virtual_aliases 2>/dev/null || true

# Create mailboxes for test users
mkdir -p /var/mail/vhosts/local/test
mkdir -p /var/mail/vhosts/local/user
chown -R vmail:vmail /var/mail/vhosts

# Configure SSL/TLS if enabled
if [ "$MAIL_TLS_ENABLED" = "true" ]; then
    echo "Configuring SSL/TLS for mail services..."

    if [ -f "$MAIL_SSL_CERT_FILE" ] && [ -f "$MAIL_SSL_KEY_FILE" ] && [ -f "$MAIL_SSL_CHAIN_FILE" ]; then
        echo "SSL certificates found, enabling TLS..."

        # Convert boolean values for both Postfix and Dovecot (expect yes/no instead of true/false)
        POSTFIX_TLS_ENABLED=$([ "$MAIL_TLS_ENABLED" = "true" ] && echo "yes" || echo "no")
        POSTFIX_REQUIRE_TLS=$([ "$MAIL_REQUIRE_TLS" = "true" ] && echo "yes" || echo "no")
        DOVECOT_TLS_ENABLED=$([ "$MAIL_TLS_ENABLED" = "true" ] && echo "yes" || echo "no")
        DOVECOT_REQUIRE_TLS=$([ "$MAIL_REQUIRE_TLS" = "true" ] && echo "yes" || echo "no")

        # Update Postfix SSL configuration with converted values
        MAIL_TLS_ENABLED="$POSTFIX_TLS_ENABLED" MAIL_REQUIRE_TLS="$POSTFIX_REQUIRE_TLS" \
        envsubst '${MAIL_TLS_ENABLED} ${MAIL_REQUIRE_TLS} ${MAIL_SSL_CERT_FILE} ${MAIL_SSL_KEY_FILE} ${MAIL_SSL_CHAIN_FILE}' \
            < /etc/postfix/ssl.cf >> /etc/postfix/main.cf

        # Update Dovecot SSL configuration with converted values
        MAIL_TLS_ENABLED="$DOVECOT_TLS_ENABLED" MAIL_REQUIRE_TLS="$DOVECOT_REQUIRE_TLS" \
        envsubst '${MAIL_TLS_ENABLED} ${MAIL_REQUIRE_TLS} ${MAIL_SSL_CERT_FILE} ${MAIL_SSL_KEY_FILE} ${MAIL_SSL_CHAIN_FILE}' \
            < /etc/dovecot/conf.d/10-ssl.conf > /etc/dovecot/conf.d/10-ssl-configured.conf

        # Remove the template file to avoid configuration conflicts
        rm -f /etc/dovecot/conf.d/10-ssl.conf

        echo "SSL/TLS configuration applied"
    else
        echo "Warning: TLS enabled but certificates not found. Running without TLS."
        echo "Certificate files expected:"
        echo "  - Certificate: $MAIL_SSL_CERT_FILE"
        echo "  - Private key: $MAIL_SSL_KEY_FILE"
        echo "  - Chain file: $MAIL_SSL_CHAIN_FILE"

        # Configure services to run without SSL/TLS
        echo "smtpd_use_tls = no" >> /etc/postfix/main.cf
        echo "smtp_use_tls = no" >> /etc/postfix/main.cf
        echo "smtpd_enforce_tls = no" >> /etc/postfix/main.cf
        echo "smtpd_tls_security_level = none" >> /etc/postfix/main.cf

        # Override submission port settings to disable TLS requirement
        cat >> /etc/postfix/master.cf << 'EOF'

# Override submission settings for fallback mode
submission inet n       -       y       -       -       smtpd
  -o syslog_name=postfix/submission
  -o smtpd_tls_security_level=none
  -o smtpd_sasl_auth_enable=no
  -o smtpd_client_restrictions=permit
EOF

        # Create a minimal Dovecot SSL config that disables SSL
        cat > /etc/dovecot/conf.d/10-ssl-configured.conf << 'EOF'
# SSL disabled - certificates not found
ssl = no
disable_plaintext_auth = no
EOF
        # Remove the template file to avoid configuration conflicts
        rm -f /etc/dovecot/conf.d/10-ssl.conf

        echo "SSL/TLS disabled due to missing certificates"
    fi
else
    echo "TLS disabled for mail services"
fi

echo "Mail server initialization complete."
echo "Test users created:"
echo "  - test@local (password: password)"
echo "  - user@local (password: password)"
echo ""
echo "Available services:"
echo "  - SMTP: port 25"
echo "  - IMAP: port 143"
echo "  - POP3: port 110"
if [ "$MAIL_TLS_ENABLED" = "true" ] && [ -f "$MAIL_SSL_CERT_FILE" ]; then
    echo "  - IMAPS: port 993 (SSL)"
    echo "  - POP3S: port 995 (SSL)"
    echo "  - SMTP-TLS: port 587 (TLS)"
fi
echo ""

# Start supervisor to manage all services
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
