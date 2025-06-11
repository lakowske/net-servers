#!/bin/bash
set -e

# Ensure Apache directories exist and have correct permissions
mkdir -p ${APACHE_RUN_DIR} ${APACHE_LOCK_DIR} ${APACHE_LOG_DIR}
chown -R www-data:www-data ${APACHE_LOG_DIR} ${APACHE_RUN_DIR} ${APACHE_LOCK_DIR}
chmod 755 ${APACHE_LOG_DIR} ${APACHE_RUN_DIR} ${APACHE_LOCK_DIR}

# Start Apache in foreground
echo "Starting Apache HTTP Server..."
exec /usr/sbin/apache2ctl -D FOREGROUND
