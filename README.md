# net-servers

[![CI](https://github.com/lakowske/net-servers/actions/workflows/ci.yml/badge.svg)](https://github.com/lakowske/net-servers/actions/workflows/ci.yml)

A comprehensive containerized development environment with Apache HTTP, Mail (Postfix + Dovecot), and DNS (BIND9) services, featuring automatic SSL/TLS certificate management.

## Features

- **Containerized Services**: Apache HTTP server, Mail server (SMTP/IMAP/POP3), DNS server
- **Automatic SSL/TLS**: Self-signed certificates generated automatically for HTTPS and mail encryption
- **Modern CLI**: Comprehensive command-line interface for container and service management
- **Configuration Management**: Centralized configuration with user, domain, and service management
- **Development Ready**: Hot-reload, port mapping, and debugging support
- **Quality Assurance**: Pre-commit hooks, comprehensive testing, and code quality tools
- **Cross-Platform**: Works on Linux, macOS, and Windows with Podman/Docker

## Quick Start

### Prerequisites

- **Python 3.8+**: For the CLI and management tools
- **Podman or Docker**: For container runtime
- **Git**: For version control

**Install Podman** (recommended):
```bash
# macOS
brew install podman
podman machine init
podman machine start

# Linux (Ubuntu/Debian)
sudo apt update && sudo apt install podman

# Linux (RHEL/CentOS/Fedora)
sudo dnf install podman
```

### Installation

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/net-servers.git
cd net-servers
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install the project in development mode:
```bash
pip install -e ".[dev]"
```

4. Install pre-commit hooks:
```bash
pre-commit install
```

### Start All Services

```bash
# Build and start all services with SSL
python -m net_servers.cli container build-all
python -m net_servers.cli container start-all
```

**Services will be available at**:
- **Apache HTTP**: http://localhost:8080 (redirects to HTTPS)
- **Apache HTTPS**: https://localhost:8443
- **Mail SMTP**: localhost:2525 (TLS on port 5870)
- **Mail IMAP**: localhost:1144 (SSL on port 9993)
- **DNS**: localhost:5354

## CLI Usage

The project provides a comprehensive command-line interface for managing containers, configuration, and certificates.

### Container Management

```bash
# Build containers
python -m net_servers.cli container build -c apache
python -m net_servers.cli container build-all

# Run containers
python -m net_servers.cli container run -c apache
python -m net_servers.cli container start-all

# Container lifecycle
python -m net_servers.cli container stop -c apache
python -m net_servers.cli container stop-all
python -m net_servers.cli container remove -c apache
python -m net_servers.cli container remove-all
python -m net_servers.cli container clean-all  # Stop, remove containers and images

# Monitoring
python -m net_servers.cli container list-containers
python -m net_servers.cli container logs -c apache --follow
python -m net_servers.cli container test -c apache
```

### SSL Certificate Management

```bash
# Automatic certificate generation (happens automatically with start-all)
python -m net_servers.cli certificates provision-self-signed --domain local.dev

# Let's Encrypt certificates (for production domains)
python -m net_servers.cli certificates provision-letsencrypt \
  --domain example.com --email admin@example.com

# Certificate information
python -m net_servers.cli certificates list
python -m net_servers.cli certificates info --domain local.dev
```

### Configuration Management

```bash
# Initialize configuration
python -m net_servers.cli config init

# User management
python -m net_servers.cli config user add \
  --username admin --email admin@local.dev
python -m net_servers.cli config user list
python -m net_servers.cli config user delete --username admin

# Domain management
python -m net_servers.cli config domain add \
  --name local.dev --a-record mail:172.20.0.10
python -m net_servers.cli config domain list

# Configuration validation and sync
python -m net_servers.cli config validate
python -m net_servers.cli config sync

# Utility commands
python -m net_servers.cli config test-email \
  --to admin@local.dev --subject "Test Email"
python -m net_servers.cli config daemon --interval 5
```

### Available Containers

| Container | Purpose | Default Ports | SSL Ports |
|-----------|---------|---------------|-----------|
| **apache** | HTTP/HTTPS web server | 8080 (HTTP) | 8443 (HTTPS) |
| **mail** | SMTP/IMAP/POP3 server | 2525, 1144, 1110 | 5870, 9993, 9995 |
| **dns** | BIND9 DNS server | 5354 (UDP/TCP) | N/A |

## Development

### Running Tests
```bash
# Run tests with coverage
pytest --cov=. --cov-report=term-missing --cov-fail-under=70 --cov-report=html

# Or use the VS Code task: Ctrl+Shift+P -> "Tasks: Run Task" -> "Run Tests with Coverage"
```

### Code Quality
```bash
# Format code
black .

# Lint code
flake8

# Run all pre-commit checks
pre-commit run --all-files
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing --cov-fail-under=70 --cov-report=html

# Run SSL/TLS integration tests
python -m pytest tests/integration/test_ssl_tls.py -v

# Run individual service tests
python -m pytest tests/integration/test_apache.py -v
python -m pytest tests/integration/test_mail.py -v
python -m pytest tests/integration/test_dns.py -v
```

### VS Code Integration

This project includes VS Code tasks for common operations:
- `Ctrl+Shift+P` -> "Tasks: Run Task" to see all available tasks
- Install the "Task Explorer" extension for a better task management experience

Available VS Code tasks:
- **Container tasks**: Build, run, stop, test each service
- **Testing tasks**: Run tests with coverage, specific test suites
- **Quality tasks**: Format code, run linting, pre-commit checks

## SSL/TLS Security

All testing containers automatically include SSL/TLS support:

### Automatic Features
- **Self-signed certificates** generated automatically for `local.dev`
- **HTTPS redirect** from HTTP to HTTPS on Apache
- **Mail encryption** with STARTTLS (SMTP), IMAPS, and POP3S
- **Security headers** for enhanced protection
- **Graceful fallback** when certificates are missing

### Testing SSL Services
```bash
# Test Apache HTTPS
curl -k https://localhost:8443

# Test mail SMTP TLS
python -c "
import smtplib
server = smtplib.SMTP('localhost', 5870)
server.starttls()  # Test TLS capability
server.quit()
print('SMTP TLS working!')
"

# Test IMAPS connection
openssl s_client -connect localhost:9993 -servername local.dev
```

## Project Structure

```
net-servers/
├── src/net_servers/           # Main Python package
│   ├── actions/               # Container management actions
│   ├── config/                # Configuration management
│   ├── cli.py                 # Main CLI interface
│   └── cli_*.py               # CLI command modules
├── docker/                    # Container definitions
│   ├── apache/                # Apache HTTP server
│   ├── mail/                  # Mail server (Postfix + Dovecot)
│   └── dns/                   # DNS server (BIND9)
├── tests/                     # Test suite
│   ├── integration/           # Integration tests
│   └── unit/                  # Unit tests
├── .github/workflows/         # GitHub Actions CI/CD
├── .vscode/                   # VS Code configuration
├── pyproject.toml             # Project configuration
└── CLAUDE.md                  # Development documentation
```

## Common Use Cases

### Web Development
```bash
# Start Apache with SSL
python -m net_servers.cli container run -c apache
# Access: https://localhost:8443
```

### Email Testing
```bash
# Start mail server with full SSL support
python -m net_servers.cli container run -c mail
# SMTP: localhost:2525, SMTP-TLS: localhost:5870
# IMAP: localhost:1144, IMAPS: localhost:9993
```

### Local DNS Development
```bash
# Start DNS server
python -m net_servers.cli container run -c dns
# Test: dig @localhost -p 5354 local.dev
```

### Full Development Environment
```bash
# Start everything with one command
python -m net_servers.cli container start-all
# All services with SSL, ready for development
```

## Troubleshooting

### Common Issues

**"Port already in use"**
```bash
# Check what's using the port
sudo netstat -tulpn | grep :8080

# Stop conflicting services
python -m net_servers.cli container stop-all

# Use different ports
python -m net_servers.cli container run -c apache --port-mapping 9080:80
```

**"SSL certificate errors"**
```bash
# Regenerate certificates
python -m net_servers.cli certificates provision-self-signed --domain local.dev

# Check certificate files
ls -la ~/.net-servers/state/certificates/local.dev/

# Use curl with self-signed certificates
curl -k https://localhost:8443
```

**"Container won't start"**
```bash
# Check logs
python -m net_servers.cli container logs -c apache

# Rebuild container
python -m net_servers.cli container build -c apache --rebuild

# Clean and start fresh
python -m net_servers.cli container clean-all
python -m net_servers.cli container build-all
python -m net_servers.cli container start-all
```

**macOS Specific Issues**
- **DNS conflicts**: Use port 5354 instead of 53 (mDNSResponder conflict)
- **Podman setup**: Run `podman machine start` if containers fail to start
- **Port permissions**: Use ports > 1024 for non-root containers

### Getting Help

- **Documentation**: See `CLAUDE.md` for detailed development information
- **Logs**: Use `python -m net_servers.cli container logs -c <service> --follow`
- **Debugging**: Exec into containers with `podman exec -it <container-name> bash`
- **Issues**: Report bugs and feature requests on GitHub

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and run the quality checks
4. Commit your changes: `git commit -m 'Add amazing feature'`
5. Push to the branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

Seth - lakowske@gmail.com
