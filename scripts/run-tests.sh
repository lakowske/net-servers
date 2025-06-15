#!/bin/bash
# Test runner script that ensures tests run in isolated testing environment

set -e

# Define isolated environment files
ORIGINAL_ENV_FILE="environments.yaml"
TEST_ENV_FILE="environments-test.yaml"
BACKUP_FILE="environments.yaml.backup"

# Create isolated test environment file if it doesn't exist
if [ ! -f "$TEST_ENV_FILE" ]; then
    echo "Creating isolated test environment configuration..."
    cat > "$TEST_ENV_FILE" << 'EOF'
current_environment: testing
environments:
- name: testing
  description: Isolated testing environment for pre-commit tests
  base_path: ./environments/testing
  domain: testing.local.dev
  admin_email: admin@local.dev
  enabled: true
  tags:
  - testing
  - integration
  - ci-cd
  - isolated
  created_at: '2024-01-01T00:00:00'
  last_used: '2024-01-01T00:00:00'
  certificate_mode: self_signed
  port_mappings: {}
EOF
fi

# Backup original environments file and switch to test config
if [ -f "$ORIGINAL_ENV_FILE" ]; then
    cp "$ORIGINAL_ENV_FILE" "$BACKUP_FILE"
fi
cp "$TEST_ENV_FILE" "$ORIGINAL_ENV_FILE"

# Ensure we restore original file on exit
trap 'if [ -f "$BACKUP_FILE" ]; then mv "$BACKUP_FILE" "$ORIGINAL_ENV_FILE"; fi' EXIT

echo "Using isolated test environment for tests..."

# Run tests (already in testing environment via the isolated config)
echo "Running tests..."
pytest --cov=src --cov-report=term-missing --cov-fail-under=70 --cov-report=html

echo "Tests completed successfully with isolated environment!"
