#!/bin/bash

# Start script for mail server container
set -e

echo "Starting mail server container..."

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
echo "local" > /etc/postfix/virtual_domains
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

echo "Mail server initialization complete."
echo "Test users created:"
echo "  - test@local (password: password)"
echo "  - user@local (password: password)"
echo ""
echo "Available services:"
echo "  - SMTP: port 25"
echo "  - IMAP: port 143"
echo "  - POP3: port 110"
echo ""

# Start supervisor to manage all services
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
