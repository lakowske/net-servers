#!/opt/net-servers/.venv/bin/python3
"""Dynamic Apache index page generator using live configuration data.

This CGI script generates the Apache index page with dynamic content including:
- Current environment information
- Live port mappings
- User count from configuration
- Service status and URLs
"""

import os
import sys
import json
import yaml
from pathlib import Path
from datetime import datetime

# Add the net-servers package to Python path
sys.path.insert(0, '/opt/net-servers/src')

def get_environment_config():
    """Get current environment configuration."""
    try:
        from net_servers.config.manager import ConfigurationManager
        config_manager = ConfigurationManager()
        env = config_manager.get_current_environment()
        return {
            'current_env': env,
            'env_config': env,
            'base_path': str(config_manager.paths.base_path),
            'config_path': str(config_manager.paths.config_path),
            'domain': getattr(env, 'domain', 'local.dev'),
            'admin_email': getattr(env, 'admin_email', 'admin@local.dev'),
        }
    except Exception as e:
        return {
            'error': str(e),
            'current_env': {'name': 'testing', 'domain': 'local.dev'},
            'base_path': '/data',
            'config_path': '/data/config',
            'domain': 'local.dev',
            'admin_email': 'admin@local.dev',
        }

def get_port_mappings():
    """Get current port mappings for the running container."""
    try:
        from net_servers.config.containers import ENVIRONMENT_PORT_MAPPINGS
        from net_servers.config.manager import ConfigurationManager

        config_manager = ConfigurationManager()
        env = config_manager.get_current_environment()
        env_name = getattr(env, 'name', 'testing')

        if env_name in ENVIRONMENT_PORT_MAPPINGS and 'apache' in ENVIRONMENT_PORT_MAPPINGS[env_name]:
            apache_ports = ENVIRONMENT_PORT_MAPPINGS[env_name]['apache']
            ports = {}
            for port_mapping in apache_ports:
                ports[port_mapping.container_port] = port_mapping.host_port
            return ports
        else:
            # Fallback to testing environment ports
            return {80: 8180, 443: 8543}
    except Exception:
        # Fallback ports
        return {80: 8180, 443: 8543}

def get_user_count():
    """Get count of configured users."""
    try:
        from net_servers.config.manager import ConfigurationManager
        config_manager = ConfigurationManager()
        users_config = config_manager.users_config
        return len(users_config.users)
    except Exception:
        return 0

def get_service_status():
    """Get status of available services."""
    try:
        services = {
            'webdav': {'name': 'WebDAV', 'icon': '📂', 'path': '/webdav/', 'enabled': True},
            'gitweb': {'name': 'Gitweb', 'icon': '📁', 'path': '/git', 'enabled': True},
        }
        return services
    except Exception:
        return {}

def get_container_info():
    """Get container runtime information."""
    try:
        info = {
            'hostname': os.environ.get('HOSTNAME', 'unknown'),
            'server_software': os.environ.get('SERVER_SOFTWARE', 'Apache'),
            'server_name': os.environ.get('SERVER_NAME', 'localhost'),
            'document_root': os.environ.get('DOCUMENT_ROOT', '/var/www/html'),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
        }
        return info
    except Exception:
        return {
            'hostname': 'unknown',
            'server_software': 'Apache',
            'server_name': 'localhost',
            'document_root': '/var/www/html',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
        }

def generate_html():
    """Generate the dynamic HTML content."""
    # Get dynamic data
    env_config = get_environment_config()
    ports = get_port_mappings()
    user_count = get_user_count()
    services = get_service_status()
    container_info = get_container_info()

    # Extract port information
    http_port = ports.get(80, 8180)
    https_port = ports.get(443, 8543)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Net Servers - Apache Container</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background: #f4f4f4;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #e74c3c;
            padding-bottom: 10px;
        }}
        .info {{
            background: #ecf0f1;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .status {{
            color: #27ae60;
            font-weight: bold;
        }}
        .dynamic {{
            background: #e8f5e8;
            border-left: 4px solid #27ae60;
        }}
        code {{
            background: #34495e;
            color: #ecf0f1;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        ul li {{
            margin: 8px 0;
        }}
        .service-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .service-card {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
        }}
        .timestamp {{
            font-size: 0.9em;
            color: #666;
            text-align: right;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Net Servers Apache Container</h1>

        <div class="info dynamic">
            <p><strong>🔄 Live Status:</strong> <span class="status">Running Successfully!</span></p>
            <p><strong>Environment:</strong> {getattr(env_config['current_env'], 'name', 'testing')}</p>
            <p><strong>Domain:</strong> {env_config['domain']}</p>
            <p><strong>Users Configured:</strong> {user_count}</p>
            <p><strong>Container:</strong> {container_info['hostname']}</p>
        </div>

        <div class="info">
            <p><strong>Server:</strong> {container_info['server_software']}</p>
            <p><strong>Base Image:</strong> Debian 12 Slim</p>
            <p><strong>Container Type:</strong> Development Server</p>
            <p><strong>Admin Contact:</strong> <a href="mailto:{env_config['admin_email']}">{env_config['admin_email']}</a></p>
        </div>

        <p>This Apache server is running in a Podman container managed by the net-servers CLI tool.</p>

        <p><strong>🛠️ Container Management:</strong></p>
        <ul>
            <li><code>python -m net_servers.cli container logs -c apache</code> - View container logs</li>
            <li><code>python -m net_servers.cli container stop -c apache</code> - Stop the container</li>
            <li><code>python -m net_servers.cli container list-containers</code> - List all containers</li>
        </ul>

        <div class="info">
            <p><strong>📊 Runtime Information:</strong></p>
            <ul>
                <li><strong>HTTP Port:</strong> {http_port} → 80</li>
                <li><strong>HTTPS Port:</strong> {https_port} → 443</li>
                <li><strong>Document Root:</strong> {container_info['document_root']}</li>
                <li><strong>Configuration Path:</strong> {env_config['config_path']}</li>
                <li><strong>Environment Base:</strong> {env_config['base_path']}</li>
            </ul>
        </div>

        <h2>🚀 Available Services</h2>
        <div class="service-grid">"""

    # Generate service cards dynamically
    for service_key, service in services.items():
        if service['enabled']:
            service_url = f"https://localhost:{https_port}{service['path']}"
            html_content += f"""
            <div class="service-card">
                <h3>{service['icon']} {service['name']}</h3>
                <p><strong>Access URL:</strong> <a href="{service_url}">{service_url}</a></p>
                <p><strong>Authentication:</strong> Required (HTTPS + Digest Auth)</p>
                <p><strong>Users:</strong> {user_count} configured</p>
            </div>"""

    html_content += f"""
        </div>

        <div class="info">
            <h3>📂 WebDAV File Storage</h3>
            <p>Secure file upload/download with cross-platform support:</p>
            <ul>
                <li><strong>Web Access:</strong> <a href="https://localhost:{https_port}/webdav/">Browse files via HTTPS</a></li>
                <li><strong>Windows:</strong> Map network drive to <code>https://localhost:{https_port}/webdav/</code></li>
                <li><strong>macOS:</strong> Connect to server at <code>https://localhost:{https_port}/webdav/</code></li>
                <li><strong>Linux:</strong> Mount with <code>davfs2</code> or access via web browser</li>
                <li><strong>Security:</strong> HTTPS-only with HTTP Digest authentication</li>
            </ul>
        </div>

        <div class="info">
            <h3>📁 Git Repository Browser</h3>
            <p>Web interface for browsing Git repositories with full history:</p>
            <ul>
                <li><strong>Repository Interface:</strong> <a href="https://localhost:{https_port}/git">Browse repositories</a></li>
                <li><strong>Sample Repository:</strong> <a href="https://localhost:{https_port}/git?p=sample.git;a=summary">sample.git</a></li>
                <li><strong>Features:</strong> Repository listing, commit history, file browsing, diffs</li>
                <li><strong>Repository Location:</strong> <code>/var/git/repositories/</code></li>
                <li><strong>Security:</strong> Same authentication as WebDAV</li>
            </ul>
        </div>

        <div class="info">
            <h3>🔐 Authentication</h3>
            <p>All services use unified HTTP Digest authentication:</p>
            <ul>
                <li><strong>Protocol:</strong> HTTP Digest (RFC 2617)</li>
                <li><strong>Users:</strong> {user_count} configured in <code>users.yaml</code></li>
                <li><strong>Domain:</strong> {env_config['domain']}</li>
                <li><strong>Admin:</strong> <a href="mailto:{env_config['admin_email']}">{env_config['admin_email']}</a></li>
            </ul>
        </div>

        <div class="timestamp">
            Generated dynamically on {container_info['timestamp']} | Environment: {getattr(env_config['current_env'], 'name', 'testing')}
        </div>
    </div>
</body>
</html>"""

    return html_content

def main():
    """Main CGI entry point."""
    # Set CGI headers
    print("Content-Type: text/html; charset=utf-8")
    print("Cache-Control: no-cache, no-store, must-revalidate")
    print("Pragma: no-cache")
    print("Expires: 0")
    print()  # Empty line to end headers

    try:
        # Generate and output HTML
        html = generate_html()
        print(html)
    except Exception as e:
        # Error fallback
        print(f"""<!DOCTYPE html>
<html>
<head><title>Apache Container - Error</title></head>
<body>
<h1>Apache Container Status</h1>
<p><strong>Status:</strong> Running (Static Mode)</p>
<p><strong>Error:</strong> Dynamic content generation failed: {e}</p>
<p><strong>Fallback:</strong> <a href="/index.html">Static index page</a></p>
</body>
</html>""")

if __name__ == "__main__":
    main()
