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
- **Coverage reporting** - target 70%
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
  - Test coverage (Pytest with 70% minimum)

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

### Core Testing and Quality Checks

- `pytest --cov=. --cov-report=term-missing --cov-fail-under=70 --cov-report=html` - Run tests with coverage
- `pytest tests/integration/ -v` - Run integration tests (fast: ~6s with persistent containers)
- `black .` - Format code
- `flake8` - Run linting
- `pre-commit install` - Install pre-commit hooks
- `pre-commit run --all-files` - Run all pre-commit checks

### Pre-Commit Testing Workflow

**Recommended before each commit:**

```bash
# 1. Run integration tests (fast with persistent containers)
pytest tests/integration/ -v

# 2. Run pre-commit checks
pre-commit run --all-files

# 3. If all pass, commit your changes
git commit -m "Your commit message"
```

**Why run integration tests?**
- Only takes ~6 seconds (optimized with persistent containers)
- Catches container configuration issues early
- Validates cross-service functionality
- Prevents deployment problems

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
4. Minimum 70% code coverage
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

### Additional F-String Colon Issues

**URL/Port Formatting Issue**: When creating URLs or port mappings with f-strings, flake8 E231 may still trigger even with proper concatenation.

```python
# ❌ Still causes E231 issues
url = f"http://localhost:{port}"
```

**Best Solution**: Use string concatenation for the colon to avoid flake8 parsing the `:` as an operator:

```python
# ✅ Flake8 compliant - avoids E231 colon parsing issues
url = "http://localhost" + ":" + f"{port}"
# or
url = f"http://localhost" + ":" + f"{port}"  # If first part needs variables
```

**Alternative**: Use `# noqa: E231` comment for legitimate cases where colons are part of URLs/addresses.

### Handling False Positive Linting Errors

Linters like flake8 occasionally produce false positives due to complex parsing edge cases. Here's how to handle them systematically:

#### 1. **Identify the Real Issue**
When flake8 reports an error, first verify if it's legitimate:
```bash
# Run flake8 directly on the file to see the exact error
flake8 path/to/file.py

# Check if the error makes sense in context
# Sometimes the line number or description doesn't match the actual issue
```

#### 2. **Common False Positive Patterns**
- **E713 "test for membership should be 'not in'"**: Can trigger on legitimate `x in y` patterns in complex expressions
- **E231 "missing whitespace after ':'"**: F-string colon parsing issues in URLs, port mappings
- **F541 "f-string missing placeholders"**: When combining f-strings with string concatenation

#### 3. **Resolution Strategies (in order of preference)**

**Option A: Refactor the Code Pattern**
```python
# Instead of triggering E713 on complex assert
assert (domain in output), f"Domain {domain} not found"

# Use explicit logic that's clearer to both humans and linters
missing_domains = [d for d in domains if d not in output]
if missing_domains:
    pytest.fail(f"Missing domains: {missing_domains}")
```

**Option B: Use Specific `# noqa` Comments**
```python
# Suppress specific error codes when the code is correct
url = f"http://localhost:{port}"  # noqa: E231
assert domain in output  # noqa: E713
```

**Option C: Use General `# noqa` for Persistent Issues**
```python
# When specific noqa doesn't work (rare edge cases)
problematic_line()  # noqa
```

**Option D: Function-Level Suppression**
```python
def test_something():  # noqa: E713
    """When multiple false positives occur in one function."""
    # Function content
```

#### 4. **Pre-commit vs Direct Flake8 Differences**
Sometimes pre-commit flake8 behaves differently than direct flake8:
```bash
# Test both to identify discrepancies
flake8 file.py                    # Direct flake8
pre-commit run flake8 --files file.py  # Pre-commit flake8

# Pre-commit may use different flake8 version or configuration
# Check .pre-commit-config.yaml for version differences
```

#### 5. **Documenting Suppressions**
When adding `# noqa` comments, document why:
```python
# noqa: E713 - False positive on legitimate membership test
assert domain in output, f"Domain {domain} not found"

# noqa: E231 - URL colon parsing issue in f-string
url = f"https://localhost:{port}"
```

#### 6. **When to Investigate vs. Suppress**
- **Investigate first**: Most linting errors are legitimate and should be fixed
- **Suppress after verification**: Only when you're confident the code is correct
- **Prefer refactoring**: If possible, rewrite to avoid the pattern triggering the false positive
- **Document patterns**: Add examples to this guide when new false positives are discovered

#### 7. **Black vs. Flake8 Conflicts**
When Black auto-formatting conflicts with `# noqa` placement:
```python
# Black may move noqa comments, test different placements
result = some_function(  # noqa: E713
    complex_args
)

# Sometimes putting noqa on a different line works better
# noqa: E713
result = some_function(complex_args)
```

**Remember**: False positives are rare. Always verify the code is actually correct before suppressing linter warnings.

## SSL/TLS Certificate Management

The project includes automatic SSL/TLS certificate management for all testing containers. This ensures that HTTPS and mail SSL services work out of the box.

### Automatic Certificate Generation

When starting testing containers, the system automatically:

1. **Creates self-signed certificates** for the configured domain (default: `local.dev`)
2. **Mounts certificates** into containers at `/data/state/certificates/{domain}/`
3. **Enables SSL services** with proper environment variables
4. **Configures fallback scenarios** when certificates are missing

### SSL-Enabled Services

#### Apache HTTPS

- **HTTP**: `http://localhost:8080` (redirects to HTTPS)
- **HTTPS**: `https://localhost:8443`
- **Features**: HTTP to HTTPS redirect, security headers, self-signed certificates

#### Mail SSL/TLS

- **SMTP TLS**: `localhost:5870` (port 587 in container)
- **IMAPS**: `localhost:9993` (port 993 in container)
- **POP3S**: `localhost:9995` (port 995 in container)
- **Features**: STARTTLS support, SSL/TLS encryption, graceful fallback

### Certificate Management Commands

```bash
# Provision self-signed certificate for a domain
python -m net_servers.cli certificates provision-self-signed --domain local.dev

# Provision Let's Encrypt certificate (requires public domain and DNS)
python -m net_servers.cli certificates provision-letsencrypt --domain example.com --email admin@example.com

# List available certificates
python -m net_servers.cli certificates list

# View certificate information
python -m net_servers.cli certificates info --domain local.dev
```

### Certificate Storage

Certificates are stored in the configuration directory:

```
~/.net-servers/state/certificates/
├── local.dev/
│   ├── cert.pem          # Certificate file
│   ├── privkey.pem       # Private key
│   └── fullchain.pem     # Full certificate chain
└── example.com/
    ├── cert.pem
    ├── privkey.pem
    └── fullchain.pem
```

### Development vs Production

**Testing Containers** (default):

- Automatically generate self-signed certificates
- SSL enabled by default for Apache and Mail services
- Certificates mounted as volumes
- Graceful fallback when certificates missing

**Production Containers**:

- Use existing certificates or Let's Encrypt
- Requires proper DNS setup for Let's Encrypt
- Manual certificate provisioning
- Production-ready SSL configuration

### SSL Testing

The project includes comprehensive SSL/TLS integration tests:

```bash
# Run SSL/TLS test suite
python -m pytest tests/integration/test_ssl_tls.py -v

# Test individual SSL components
python -m pytest tests/integration/test_ssl_tls.py::TestApacheSSL -v
python -m pytest tests/integration/test_ssl_tls.py::TestMailSSL -v
```

**Test Coverage**:

- Apache HTTPS functionality (HTTP redirect, content serving, certificate validation)
- Mail SSL/TLS services (SMTP STARTTLS, IMAPS, POP3S)
- Certificate provisioning and validation
- SSL fallback scenarios for missing certificates

### Troubleshooting SSL Issues

**Common Issues and Solutions**:

1. **"SSL certificates not found"**

   ```bash
   # Check certificate directory
   ls -la ~/.net-servers/state/certificates/local.dev/

   # Regenerate certificates
   python -m net_servers.cli certificates provision-self-signed --domain local.dev
   ```

2. **"Certificate verification failed"**

   - Use `-k` flag with curl for self-signed certificates
   - Add certificate to system trust store for production

3. **"Connection refused on SSL ports"**

   ```bash
   # Check container logs
   python -m net_servers.cli container logs -c apache

   # Verify SSL environment variables
   podman exec net-servers-apache-testing printenv | grep SSL
   ```

4. **"Mail SSL services not working"**
   ```bash
   # Test SMTP TLS manually
   python -c "
   import smtplib
   server = smtplib.SMTP('localhost', 5870)
   server.starttls()
   print('SMTP TLS working!')
   server.quit()
   "
   ```

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

## Environment Management System

The project includes a sophisticated environment management system that allows you to maintain multiple isolated environments (development, staging, production, etc.) with separate configurations and state.

### Environment Architecture

**Environment Isolation:**

Each environment maintains its own complete directory structure:

```
/data/
├── development/          # Development environment
│   ├── config/
│   ├── state/
│   ├── logs/
│   └── code/
├── staging/              # Staging environment
│   ├── config/
│   ├── state/
│   ├── logs/
│   └── code/
└── production/           # Production environment
    ├── config/
    ├── state/
    ├── logs/
    └── code/
```

**Environment Configuration (`environments.yaml`):**

```yaml
current_environment: development
environments:
  - name: development
    description: Development environment for local testing
    base_path: /Users/seth/.net-servers/development
    domain: local.dev
    admin_email: admin@local.dev
    enabled: true
    tags: [development, local]
    created_at: '2024-06-14T10:30:00'
    last_used: '2024-06-14T15:45:00'

  - name: staging
    description: Staging environment for pre-production testing
    base_path: /Users/seth/.net-servers/staging
    domain: staging.local.dev
    admin_email: admin@local.dev
    enabled: true
    tags: [staging, testing, pre-production]
    created_at: '2024-06-14T10:30:00'
    last_used: '2024-06-10T14:20:00'

  - name: production
    description: Production environment for live services
    base_path: /Users/seth/.net-servers/production
    domain: example.com
    admin_email: admin@example.com
    enabled: false
    tags: [production, live, critical]
    created_at: '2024-06-14T10:30:00'
    last_used: '2024-06-01T09:15:00'
```

### Environment Management Commands

#### Listing and Information

```bash
# List all environments
python -m net_servers.cli environments list

# List in JSON format
python -m net_servers.cli environments list --format json

# Show only enabled environments
python -m net_servers.cli environments list --enabled-only

# Show current environment details
python -m net_servers.cli environments current

# Show detailed environment information
python -m net_servers.cli environments info staging
```

#### Environment Lifecycle

```bash
# Create a new environment
python -m net_servers.cli environments add testing \
  --description "Testing environment for CI/CD" \
  --base-path /data/testing \
  --domain test.local.dev \
  --admin-email admin@local.dev \
  --tag testing --tag ci-cd --tag automated

# Switch to different environment
python -m net_servers.cli environments switch staging

# Enable/disable environments
python -m net_servers.cli environments enable production
python -m net_servers.cli environments disable old-env

# Remove environment (with confirmation)
python -m net_servers.cli environments remove old-env
python -m net_servers.cli environments remove old-env --force
```

#### Configuration Management

```bash
# Initialize default environments
python -m net_servers.cli environments init

# Force reinitialize (overwrites existing)
python -m net_servers.cli environments init --force

# Validate environment configuration
python -m net_servers.cli environments validate
```

### Environment Features

#### Automatic State Management

When switching environments, the system automatically:

1. **Updates current environment** in `environments.yaml`
2. **Updates last used timestamp** for the target environment
3. **Reinitializes configuration manager** with new base path
4. **Creates directory structure** if it doesn't exist
5. **Clears configuration cache** to reload from new environment

#### Safety Features

- **Cannot remove current environment**: Prevents accidental deletion
- **Cannot disable current environment**: Ensures system stability
- **Validation checks**: Comprehensive validation of all environment settings
- **Confirmation prompts**: Interactive confirmation for destructive operations

#### Environment Validation

The validation system checks:

- **Current environment exists** and is enabled
- **Email format validation** for admin emails
- **Absolute path validation** for base paths
- **Domain format validation** (basic checks)
- **No duplicate environment names**
- **At least one environment enabled**

### Integration with Container System

When running containers with environment management:

```python
# Configuration manager automatically uses current environment
config_manager = ConfigurationManager()
current_env = config_manager.get_current_environment()

# All operations use environment-specific paths:
# - Base path: current_env.base_path
# - Domain: current_env.domain
# - Admin email: current_env.admin_email
```

### Development Workflow with Environments

#### 1. Daily Development

```bash
# Start in development environment
python -m net_servers.cli environments switch development

# Build and test containers
python -m net_servers.cli container build-all
python -m net_servers.cli container run -c apache
```

#### 2. Pre-production Testing

```bash
# Switch to staging for integration testing
python -m net_servers.cli environments switch staging

# Deploy and test with staging data
python -m net_servers.cli container run -c mail
```

#### 3. Production Deployment

```bash
# Switch to production environment
python -m net_servers.cli environments switch production

# Deploy with production configuration
python -m net_servers.cli container start-all
```

### Environment Best Practices

#### Naming Conventions

- **development**: Local development work
- **staging**: Pre-production testing
- **production**: Live production services
- **testing**: Automated testing environments
- **feature-{name}**: Feature-specific environments

#### Tag Organization

Use tags to organize environments:

- **Environment type**: `development`, `staging`, `production`
- **Purpose**: `testing`, `ci-cd`, `demo`
- **Criticality**: `critical`, `non-critical`
- **Team**: `backend`, `frontend`, `qa`

#### Directory Structure

Recommended base path patterns:

- **Development**: `~/.net-servers/development`
- **Staging**: `/data/staging` or `~/.net-servers/staging`
- **Production**: `/data/production`
- **Testing**: `/tmp/net-servers-testing` (ephemeral)

### Environment Migration

When moving between systems or upgrading:

1. **Export environment list**: Use `--format json` to get machine-readable config
2. **Copy state directories**: Transfer entire base_path directories
3. **Update paths**: Modify base_path values for new system
4. **Validate configuration**: Run validation after migration

The environment management system provides complete isolation between different deployment stages while maintaining operational simplicity and safety.

## Environment Configuration

The project includes a default `environments.yaml` configuration file that provides working defaults for all developers and CI environments.

### Default Configuration

The repository includes a default `environments.yaml` with:
- **Relative paths**: `./environments/*` that work in any project directory
- **Standard domains**: `local.dev` for development, `example.com` for production
- **Four environments**: development (default), testing, staging, production
- **Self-signed certificates**: For local development and testing

### Personal Overrides

To customize environments for your local setup:

1. **Copy the default**: `cp environments.yaml environments.yaml.personal`
2. **Modify your copy**: Edit `environments.yaml.personal` with your preferences
3. **Use your config**: The system automatically uses `environments.yaml.personal` if it exists

The `environments.yaml.personal` file is ignored by git, so your personal settings won't be committed.

### Benefits

- **CI Compatibility**: Tests run immediately without setup
- **Developer Onboarding**: New developers get working configuration
- **Flexibility**: Support both relative and absolute paths
- **Personal Privacy**: Personal configurations stay local

## Commit Message Guidelines

- Use clear, concise commit messages that describe the change
- Do not include AI assistant attribution or advertising in commit messages
- Focus on the "why" rather than the "what" in commit descriptions
