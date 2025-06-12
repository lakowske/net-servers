#!/bin/bash

# Start script for DNS server container
set -e

echo "Starting DNS server container..."

# Create required directories
mkdir -p /var/log/bind
mkdir -p /var/cache/bind
mkdir -p /var/lib/bind
mkdir -p /etc/bind/zones

# Set proper permissions
chown -R bind:bind /var/log/bind /var/cache/bind /var/lib/bind /etc/bind
chmod 755 /var/log/bind /var/cache/bind /var/lib/bind /etc/bind/zones
chmod 644 /etc/bind/*.conf /etc/bind/zones/*

# Generate RNDC key if it doesn't exist
if [ ! -f /etc/bind/rndc.key ]; then
    echo "Generating RNDC key..."
    rndc-confgen -a -b 512 -k rndc-key
    chown bind:bind /etc/bind/rndc.key
    chmod 640 /etc/bind/rndc.key
fi

# Validate configuration files
echo "Validating BIND configuration..."
if ! named-checkconf /etc/bind/named.conf; then
    echo "ERROR: BIND configuration is invalid!"
    exit 1
fi

# Validate zone files
echo "Validating zone files..."
if ! named-checkzone local.dev /etc/bind/zones/db.local.zone; then
    echo "ERROR: Forward zone file is invalid!"
    exit 1
fi

if ! named-checkzone 0.168.192.in-addr.arpa /etc/bind/zones/db.local.rev; then
    echo "ERROR: Reverse zone file is invalid!"
    exit 1
fi

echo "DNS server initialization complete."
echo ""
echo "Configuration details:"
echo "  - Domain: local.dev"
echo "  - Name server: ns1.local.dev (192.168.1.10)"
echo "  - Web server: www.local.dev, apache.local.dev (192.168.1.11)"
echo "  - Mail server: mail.local.dev (192.168.1.12)"
echo ""
echo "Available services:"
echo "  - DNS: port 53 (UDP/TCP)"
echo "  - Query logging enabled"
echo "  - Dynamic updates allowed from localhost"
echo ""
echo "Test DNS resolution:"
echo "  dig @localhost www.local.dev A"
echo "  dig @localhost mail.local.dev MX"
echo ""

# Start BIND in foreground
echo "Starting BIND DNS server..."
exec /usr/sbin/named -g -c /etc/bind/named.conf -u bind
