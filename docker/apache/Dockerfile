# Apache HTTP Server with Debian base
FROM debian:12-slim

# Set metadata
LABEL maintainer="Seth <lakowske@gmail.com>"
LABEL description="Apache HTTP Server on Debian for development"
LABEL version="1.0"

# Set environment variables
ENV APACHE_RUN_USER=www-data \
    APACHE_RUN_GROUP=www-data \
    APACHE_LOG_DIR=/var/log/apache2 \
    APACHE_PID_FILE=/var/run/apache2/apache2.pid \
    APACHE_RUN_DIR=/var/run/apache2 \
    APACHE_LOCK_DIR=/var/lock/apache2 \
    DEBIAN_FRONTEND=noninteractive

# Update package list and install Apache with SSL support, Git, Gitweb, and Python for CLI
RUN apt-get update && \
    apt-get install -y \
        apache2 \
        apache2-utils \
        curl \
        net-tools \
        iproute2 \
        certbot \
        python3-certbot-apache \
        openssl \
        ca-certificates \
        gettext-base \
        python3 \
        python3-pip \
        python3-venv \
        git \
        gitweb \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy configuration files
COPY docker/apache/config/apache-extra.conf /etc/apache2/conf-available/
COPY docker/apache/config/webdav.conf /etc/apache2/conf-available/
COPY docker/apache/config/gitweb.conf /etc/apache2/conf-available/
COPY docker/apache/config/gitweb-config.perl /etc/gitweb.conf
COPY docker/apache/config/000-default.conf /etc/apache2/sites-available/
COPY docker/apache/config/ssl-vhost.conf /etc/apache2/sites-available/
COPY docker/apache/config/start-apache.sh /usr/local/bin/
COPY docker/apache/content/index.html /var/www/html/
COPY docker/apache/content/index.cgi /var/www/html/
COPY docker/apache/content/webdav-header.html /var/www/webdav/
COPY docker/apache/content/webdav-footer.html /var/www/webdav/
COPY docker/apache/content/gitweb-header.html /var/www/
COPY docker/apache/content/gitweb-footer.html /var/www/

# Configure Apache with SSL, WebDAV, and Gitweb support
RUN a2enconf apache-extra && \
    a2enconf webdav && \
    a2enconf gitweb && \
    a2enmod rewrite headers deflate ssl dav dav_fs dav_lock auth_digest cgi && \
    a2ensite 000-default && \
    chmod +x /usr/local/bin/start-apache.sh && \
    mkdir -p /data/state/certificates && \
    mkdir -p /var/www/webdav && \
    mkdir -p /var/lock/apache2/webdav && \
    mkdir -p /var/git/repositories && \
    chown -R www-data:www-data /var/git

# Set proper ownership and permissions
RUN chown -R www-data:www-data /var/www/html && \
    chown -R www-data:www-data /var/www/webdav && \
    chown -R www-data:www-data /var/lock/apache2/webdav && \
    chmod 755 /var/www/webdav && \
    chmod 755 /var/lock/apache2/webdav && \
    chmod +x /var/www/html/index.cgi && \
    mkdir -p ${APACHE_RUN_DIR} ${APACHE_LOCK_DIR} ${APACHE_LOG_DIR} && \
    chown -R www-data:www-data ${APACHE_LOG_DIR} ${APACHE_RUN_DIR} ${APACHE_LOCK_DIR} && \
    chmod 755 ${APACHE_LOG_DIR} ${APACHE_RUN_DIR} ${APACHE_LOCK_DIR}

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
    CMD curl -f http://localhost/ || exit 1

# Expose HTTP and HTTPS ports
EXPOSE 80 443

# Use custom startup script
CMD ["/usr/local/bin/start-apache.sh"]
