# Clean Python Project Template

## Project Purpose
This is a template for creating clean, professional Python projects that incorporate industry best practices from the start. It serves as a foundation for new Python projects with all the essential development tools and quality assurance measures pre-configured.

## Clean Code Practices Implemented

### Code Quality & Standards
- **Black** - Automatic code formatting with 88 character line length
- **Flake8** - Comprehensive linting with Google docstring conventions
- **Pre-commit hooks** - Automated quality checks before every commit

### Testing & Coverage
- **Pytest** - Modern testing framework with proper project structure
- **Coverage reporting** - Currently at 40% (temporary while building config system), target 80%
- **HTML coverage reports** - Generated in `htmlcov/` directory
- **Integration testing** - Structured test organization

### Git Workflow
- **Pre-commit configuration** - Ensures code quality on every commit
- **Automated checks** for:
  - Trailing whitespace removal
  - End-of-file fixing
  - YAML validation
  - Large file detection
  - Code formatting (Black)
  - Linting (Flake8)
  - Test coverage (Pytest with 80% minimum)

## Project Structure
```
clean-python/
├── actions/          # Project build and automation scripts
├── tests/           # Test suite with pytest configuration
├── build/           # Build artifacts (auto-generated)
├── htmlcov/         # HTML coverage reports
├── .pre-commit-config.yaml  # Pre-commit hook configuration
├── .flake8          # Flake8 linting configuration
├── setup.cfg        # Project metadata and configuration
└── pyproject.toml   # Modern Python project configuration and dependencies
```

## Development Commands
- `pytest --cov=. --cov-report=term-missing --cov-fail-under=80 --cov-report=html` - Run tests with coverage
- `black .` - Format code
- `flake8` - Run linting
- `pre-commit install` - Install pre-commit hooks
- `pre-commit run --all-files` - Run all pre-commit checks

## CLI Interface

This project provides a comprehensive CLI for managing containerized network services.

### Main CLI Structure
```bash
python -m net_servers.cli [OPTIONS] COMMAND [ARGS]...
```

### Available Commands

#### Container Management
```bash
# List available container configurations
python -m net_servers.cli container list-configs

# Build container images
python -m net_servers.cli container build -c apache
python -m net_servers.cli container build-all

# Run containers
python -m net_servers.cli container run -c apache --port-mapping 8080:80
python -m net_servers.cli container run -c mail
python -m net_servers.cli container run -c dns --port-mapping 5353:53

# Container lifecycle management
python -m net_servers.cli container start-all
python -m net_servers.cli container stop -c apache
python -m net_servers.cli container stop-all
python -m net_servers.cli container remove -c apache
python -m net_servers.cli container remove-all
python -m net_servers.cli container clean-all

# Container inspection
python -m net_servers.cli container list-containers
python -m net_servers.cli container logs -c apache

# Integration testing
python -m net_servers.cli container test -c apache
```

#### Configuration Management
```bash
# Initialize configuration system
python -m net_servers.cli config init

# Validate configurations
python -m net_servers.cli config validate

# Sync configurations to services
python -m net_servers.cli config sync

# User management
python -m net_servers.cli config user add --username admin --email admin@local.dev
python -m net_servers.cli config user list
python -m net_servers.cli config user delete --username admin

# Domain management
python -m net_servers.cli config domain add --name local.dev --a-record mail:172.20.0.10
python -m net_servers.cli config domain list

# Utility commands
python -m net_servers.cli config test-email --to admin@local.dev --subject "Test"
python -m net_servers.cli config daemon --interval 5
```

### Container Services

#### Apache HTTP Server
- **Purpose**: Development web server
- **Default Port**: 8080 (mapped to container port 80)
- **Access**: http://localhost:8080
- **Configuration**: `docker/apache/config/`

#### Mail Server (Postfix + Dovecot)
- **Purpose**: SMTP/IMAP/POP3 email services
- **Ports**: 25 (SMTP), 143 (IMAP), 110 (POP3), 587 (SMTP-TLS), 993 (IMAPS), 995 (POP3S)
- **Configuration**: Multi-service container with Supervisor
- **Authentication**: Custom user management system

#### DNS Server (BIND9)
- **Purpose**: Local DNS resolution and zone management
- **Default Port**: 53 (use 5353 on macOS to avoid conflicts)
- **Configuration**: Dynamic zone file generation
- **Usage**: Custom domain resolution for development

## macOS Setup Guide

This section addresses common infrastructure issues that new macOS users might encounter when setting up the project.

### Prerequisites

1. **Podman Installation**
   ```bash
   brew install podman
   podman machine init
   podman machine start
   ```

2. **Python Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. **Pre-commit Setup**
   ```bash
   pre-commit install
   ```

### Common macOS Issues and Solutions

#### 1. DNS Port 53 Conflicts
**Issue**: DNS container fails with "port 53 already in use"
**Cause**: macOS runs mDNSResponder on port 53
**Solution**: Use alternative port mapping
```bash
# Instead of default port 53
python -m net_servers.cli container run -c dns --port-mapping 5353:53

# Test DNS resolution
dig @127.0.0.1 -p 5353 local.dev
```

#### 2. Container Build Requirements
**Issue**: Integration tests fail because container images don't exist
**Solution**: Build containers before running tests
```bash
# Build all containers
python -m net_servers.cli container build-all

# Or build individually
python -m net_servers.cli container build -c apache
python -m net_servers.cli container build -c mail
python -m net_servers.cli container build -c dns
```

#### 3. Container Name Conflicts
**Issue**: "Container name already in use" errors
**Solution**: Clean up existing containers
```bash
# Stop all containers
python -m net_servers.cli container stop-all

# Remove specific container
python -m net_servers.cli container remove -c dns

# Complete cleanup
python -m net_servers.cli container clean-all
```

#### 4. Port Accessibility Testing
**Quick connectivity tests:**
```bash
# Test Apache (HTTP)
curl -f http://localhost:8080

# Test Mail (SMTP)
nc -z localhost 25

# Test DNS (custom port)
dig @127.0.0.1 -p 5353 local.dev
```

### Integration Testing on macOS

#### Running Tests Successfully
1. **Build containers first**: `python -m net_servers.cli container build-all`
2. **Clean up existing containers**: `python -m net_servers.cli container clean-all`
3. **Run tests with proper ports**: Tests automatically handle port conflicts

#### Expected Test Results
- ✅ **Unit tests**: All 196+ tests should pass
- ✅ **Basic container functionality**: Container startup and basic connectivity
- ⚠️ **DNS resolution tests**: May fail due to system resolver conflicts (expected)
- ✅ **Apache/Mail services**: Should work properly with port mapping

#### Troubleshooting Failed Tests
```bash
# Check container logs
python -m net_servers.cli container logs -c mail

# Verify container status
python -m net_servers.cli container list-containers

# Test individual services
python -m net_servers.cli container test -c apache
```

### Development Workflow on macOS

1. **Initial Setup**
   ```bash
   git clone <repo>
   cd net-servers
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   pre-commit install
   ```

2. **Build and Test**
   ```bash
   python -m net_servers.cli container build-all
   pytest tests/test_*.py  # Run unit tests
   python -m net_servers.cli container run -c apache --port-mapping 8080:80
   ```

3. **Clean Development Environment**
   ```bash
   python -m net_servers.cli container clean-all
   pre-commit run --all-files
   ```

## Quality Gates
Every commit must pass:
1. Code formatting (Black)
2. Linting checks (Flake8)
3. All tests passing
4. Minimum 80% code coverage
5. No trailing whitespace
6. Proper file endings
7. Valid YAML syntax

This template ensures that code quality, testing, and documentation standards are maintained throughout the development lifecycle.

## Coding Standards and Common Issues

### Flake8 F-String Guidelines
Flake8 has specific rules around f-strings that can cause unexpected violations:

**Issue**: Flake8 E231 (missing whitespace after ':') and F541 (f-string missing placeholders)
```python
# ❌ Flake8 violations
port_mapping = f"{self.config.port}:80"  # E231: missing space after ':'
cmd.extend(["-p", f"25:25"])  # F541: f-string without variables
```

**Solution**: Break f-strings at colons and use regular strings for static values
```python
# ✅ Flake8 compliant
port_mapping = f"{self.config.port}" + ":80"  # Split at colon
cmd.extend(["-p", "25:25"])  # Regular string for static values
```

**General Rule**: When f-strings contain colons followed by static content, break the string at the colon and concatenate with a regular string to avoid flake8 parsing issues.

## Adding New Container Services

This project supports containerized services with automated build, test, and deployment workflows. Follow this systematic process when adding new services:

### 1. Container Setup
- **Create service directory**: `docker/{service-name}/`
- **Write Dockerfile**: Use existing services as templates (e.g., `docker/apache/Dockerfile`)
- **Use consistent base image**: `debian:12-slim` for efficiency and consistency
- **Add configuration files**: Place all configs in `docker/{service-name}/config/`
- **Create startup script**: Custom script for multi-service initialization

### 2. CLI Integration
- **Update container config**: Add service to `src/net_servers/config/containers.py`
- **Test CLI commands**: Verify build, run, stop, and clean operations work
- **Example commands**:
  ```bash
  python -m net_servers.cli build -c {service-name}
  python -m net_servers.cli run -c {service-name}
  python -m net_servers.cli test -c {service-name}
  ```

### 3. Integration Testing
- **Create test file**: `tests/integration/test_{service-name}.py`
- **Use session-scoped fixtures**: Reuse containers across tests for performance
- **Test systematically**:
  1. Container startup and health
  2. Service communication (ports accessible)
  3. Service-specific functionality
  4. Authentication (if applicable)
  5. End-to-end workflows
  6. Log accessibility
- **Keep containers running**: For debugging failed tests
- **Use 2-second timeouts**: For fast local testing

### 4. VS Code Tasks Integration
- **Update `.vscode/tasks.json`**: Add build, run, and test tasks for new service
- **Task naming pattern**: `{Service} - {Action}` (e.g., "Mail - Build", "Mail - Test")
- **Task dependencies**: Ensure proper build → run → test sequence

### 5. Quality Assurance
- **Run pre-commit checks**: Ensure new code passes all quality gates
- **Test coverage**: Add unit tests if new business logic is introduced
- **Documentation**: Update README or service-specific docs as needed

### 6. Debugging Process
When tests fail:
1. **Check container logs**: `podman logs {container-name}`
2. **Exec into container**: `podman exec -it {container-name} bash`
3. **Inspect config files**: Verify all configuration is correctly applied
4. **Test service communication**: Use basic connectivity tests first
5. **Check authentication**: Verify user/credential setup if applicable

### Example: Mail Service Implementation
The mail service demonstrates this complete workflow:
- **Multi-service container**: Postfix (SMTP) + Dovecot (IMAP/POP3) + Supervisor
- **Configuration management**: Separate config files for each service
- **User credential setup**: Dynamic user creation in startup script
- **Authentication debugging**: Custom Dovecot auth to override system defaults
- **Complete test coverage**: 11 integration tests covering all functionality
- **Fast testing**: 2-second timeouts for quick feedback

## Configuration Management System

This project includes a comprehensive configuration management system designed for persistent, dynamic service configuration across container restarts.

### Configuration Architecture

**Directory Structure:**
```
/data/
├── config/                    # Central configuration store
│   ├── global.yaml           # Global system configuration
│   ├── users.yaml            # User definitions
│   ├── domains.yaml          # Domain configurations
│   └── services/             # Service-specific configs
│       └── services.yaml
├── state/                    # Runtime state data
│   ├── mailboxes/
│   ├── dns-zones/
│   └── certificates/
├── code/                     # Live code mounting for development
│   └── net_servers/          # Python package mounted for iteration
└── logs/                     # Centralized logging
```

### Volume Management

**Development vs Production Modes:**
- **Development**: Code volumes are read-write for live editing
- **Production**: Code volumes can be read-only for security

**Volume Types:**
- **Configuration volumes**: Persistent settings and schema definitions
- **State volumes**: Runtime data like mailboxes, DNS zones, certificates
- **Code volumes**: Source code for development iteration
- **Log volumes**: Centralized logging across all services

### Configuration Schema

**Global Configuration (`global.yaml`):**
```yaml
system:
  domain: "local.dev"
  admin_email: "admin@local.dev"
  timezone: "UTC"
```

**User Configuration (`users.yaml`):**
```yaml
users:
  - username: "admin"
    email: "admin@local.dev"
    domains: ["local.dev"]
    roles: ["admin"]
    mailbox_quota: "1G"
```

**Domain Configuration (`domains.yaml`):**
```yaml
domains:
  - name: "local.dev"
    mx_records: ["mail.local.dev"]
    a_records:
      mail: "172.20.0.10"
      www: "172.20.0.20"
```

### Configuration-to-Service Pattern

**Workflow:**
1. **Configuration Change** → Parse & Validate → Generate Service Files → Apply Changes → Reload Services
2. **Cross-service consistency** through centralized domain and user management
3. **Service coordination** via shared configuration schemas

**Example Implementation:**
```python
# Enable configuration management
config = get_container_config("mail", use_config_manager=True)

# Configuration manager automatically adds:
# - Volume mounts for persistent data
# - Environment variables from global config
# - Service-specific state directories
```

### Usage Patterns

**Basic Container Operations (Backward Compatible):**
```bash
python -m net_servers.cli build -c mail    # Uses basic config
python -m net_servers.cli run -c mail      # No persistent volumes
```

**Advanced Configuration Management:**
```python
from net_servers.config.manager import ConfigurationManager

# Initialize with persistent configuration
config_manager = ConfigurationManager(base_path="/data")
config_manager.initialize_default_configs()

# Get enhanced container config with volumes and environment
container_config = get_container_config("mail", use_config_manager=True)
```

### Benefits

1. **Persistence**: Configuration survives container restarts
2. **Development Speed**: Live code mounting for rapid iteration
3. **Centralized Management**: Single source of truth for all configuration
4. **Service Coordination**: Cross-service configuration consistency
5. **Scalability**: Easy to add new services following the same pattern

## Commit Message Guidelines

- Use clear, concise commit messages that describe the change
- Do not include AI assistant attribution or advertising in commit messages
- Focus on the "why" rather than the "what" in commit descriptions
