# Integration Tests

This directory contains integration tests for container services that require a running Podman environment.

## Prerequisites

- Podman installed and accessible via command line
- Python packages: `pytest`, `requests`
- Container images built (use `python -m net_servers.cli build-all`)

## Running Tests

### Via CLI (Recommended)
```bash
# Test all containers
python -m net_servers.cli test

# Test specific container
python -m net_servers.cli test --config apache
python -m net_servers.cli test --config mail

# Build and test
python -m net_servers.cli test --build --verbose
```

### Direct pytest execution
```bash
# Test all containers
pytest tests/integration/

# Test specific container
pytest tests/integration/test_apache.py
pytest tests/integration/test_mail.py

# Verbose output
pytest tests/integration/ -v -s
```

## Test Coverage

### Apache Container Tests
- Container startup and readiness
- HTTP service response and custom content
- Apache configuration and modules
- Error handling (404 responses)
- Log accessibility
- Process verification
- Port listening verification

### Mail Container Tests
- Container startup and readiness
- Mail services (Postfix, Dovecot) running
- Port accessibility (SMTP, IMAP, POP3)
- Basic protocol communication
- User authentication (test users)
- Complete email workflow (send via SMTP, receive via IMAP)
- Mail directory structure
- Service configuration verification
- Log accessibility

## Test Users

The mail container includes pre-configured test users for integration testing:
- `test@local` (password: `password`)
- `user@local` (password: `password`)

## Notes

- These tests are **not** included in pre-commit hooks due to infrastructure requirements
- Tests automatically manage container lifecycle (start/stop/cleanup)
- Tests use dynamic port mapping to avoid conflicts
- Each test class uses container fixtures that ensure proper cleanup
- Integration tests should be run in CI/CD environments with Podman support
