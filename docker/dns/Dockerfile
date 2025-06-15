# DNS Server with BIND on Debian base
FROM debian:12-slim

# Set metadata
LABEL maintainer="Seth <lakowske@gmail.com>"
LABEL description="DNS Server with BIND on Debian for development"
LABEL version="1.0"

# Set environment variables
ENV BIND_USER=bind \
    BIND_GROUP=bind \
    BIND_UID=107 \
    BIND_GID=115 \
    BIND_DIR=/var/lib/bind \
    BIND_CACHE_DIR=/var/cache/bind \
    BIND_LOG_DIR=/var/log/bind \
    DEBIAN_FRONTEND=noninteractive

# Update package list and install BIND packages and Python for CLI
RUN apt-get update && \
    apt-get install -y \
        bind9 \
        bind9-utils \
        bind9-dnsutils \
        bind9-host \
        curl \
        net-tools \
        iproute2 \
        python3 \
        python3-pip \
        python3-venv \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy configuration files
COPY docker/dns/config/named.conf /etc/bind/named.conf
COPY docker/dns/config/named.conf.options /etc/bind/named.conf.options
COPY docker/dns/config/named.conf.local /etc/bind/named.conf.local
COPY docker/dns/config/db.local.zone /etc/bind/zones/db.local.zone
COPY docker/dns/config/db.local.rev /etc/bind/zones/db.local.rev
COPY docker/dns/config/start-dns.sh /usr/local/bin/

# Create necessary directories and set permissions
RUN mkdir -p /etc/bind/zones ${BIND_LOG_DIR} && \
    chown -R ${BIND_USER}:${BIND_GROUP} /etc/bind /var/lib/bind /var/cache/bind ${BIND_LOG_DIR} && \
    chmod 755 /etc/bind/zones ${BIND_LOG_DIR} && \
    chmod 644 /etc/bind/*.conf /etc/bind/zones/* && \
    chmod +x /usr/local/bin/start-dns.sh

# Install CLI package and dependencies during build
# Copy source code and pyproject.toml
COPY src/ /opt/net-servers/src/
COPY pyproject.toml /opt/net-servers/
RUN cd /opt/net-servers && \
    python3 -m venv .venv && \
    .venv/bin/pip install --upgrade pip && \
    .venv/bin/pip install -e .

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD dig @127.0.0.1 localhost A +short || exit 1

# Expose DNS ports (UDP and TCP)
EXPOSE 53/udp 53/tcp

# Use custom startup script
CMD ["/usr/local/bin/start-dns.sh"]
