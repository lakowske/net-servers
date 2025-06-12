# Mail Server with Dovecot and Postfix on Debian base
FROM debian:12-slim

# Set metadata
LABEL maintainer="Seth <lakowske@gmail.com>"
LABEL description="Mail Server with Dovecot and Postfix on Debian for development"
LABEL version="1.0"

# Set environment variables
ENV MAIL_USER=vmail \
    MAIL_GROUP=vmail \
    MAIL_UID=5000 \
    MAIL_GID=5000 \
    MAIL_DIR=/var/mail/vhosts \
    POSTFIX_LOG_DIR=/var/log/postfix \
    DOVECOT_LOG_DIR=/var/log/dovecot \
    DEBIAN_FRONTEND=noninteractive

# Update package list and install mail packages
RUN apt-get update && \
    apt-get install -y \
        postfix \
        postfix-mysql \
        dovecot-core \
        dovecot-imapd \
        dovecot-pop3d \
        dovecot-lmtpd \
        dovecot-mysql \
        default-mysql-client \
        rsyslog \
        supervisor \
        curl \
        telnet \
        procps \
        net-tools \
        iproute2 \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create mail user and group
RUN groupadd -g ${MAIL_GID} ${MAIL_GROUP} && \
    useradd -r -u ${MAIL_UID} -g ${MAIL_GROUP} -d ${MAIL_DIR} -s /bin/false ${MAIL_USER}

# Copy configuration files
COPY docker/mail/config/postfix-main.cf /etc/postfix/main.cf
COPY docker/mail/config/postfix-master.cf /etc/postfix/master.cf
COPY docker/mail/config/dovecot.conf /etc/dovecot/dovecot.conf
COPY docker/mail/config/dovecot-auth-sql.conf.ext /etc/dovecot/conf.d/auth-sql.conf.ext
COPY docker/mail/config/dovecot-10-mail.conf /etc/dovecot/conf.d/10-mail.conf
COPY docker/mail/config/dovecot-10-master.conf /etc/dovecot/conf.d/10-master.conf
COPY docker/mail/config/dovecot-10-auth.conf /etc/dovecot/conf.d/10-auth.conf
COPY docker/mail/config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/mail/config/start-mail.sh /usr/local/bin/

# Create necessary directories and set permissions
RUN mkdir -p ${MAIL_DIR} ${POSTFIX_LOG_DIR} ${DOVECOT_LOG_DIR} && \
    chown -R ${MAIL_USER}:${MAIL_GROUP} ${MAIL_DIR} && \
    chown -R postfix:postfix ${POSTFIX_LOG_DIR} && \
    chown -R dovecot:dovecot ${DOVECOT_LOG_DIR} && \
    chmod 755 ${MAIL_DIR} ${POSTFIX_LOG_DIR} ${DOVECOT_LOG_DIR} && \
    chmod +x /usr/local/bin/start-mail.sh

# Configure Postfix
RUN postconf -e 'mydestination = localhost' && \
    postconf -e 'mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128 172.16.0.0/12 192.168.0.0/16 10.0.0.0/8'

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f smtp://localhost:25 || exit 1

# Expose SMTP, IMAP, and POP3 ports
EXPOSE 25 143 110 993 995 587

# Use custom startup script
CMD ["/usr/local/bin/start-mail.sh"]
