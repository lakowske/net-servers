"""Integration tests for DNS server container."""

import socket
import subprocess
import time
from typing import Any, Dict

import pytest

from net_servers.actions.container import ContainerManager
from net_servers.config.containers import get_container_config


@pytest.fixture(scope="session")
def dns_container():
    """Build and run DNS container for testing session."""
    config = get_container_config("dns")
    manager = ContainerManager(config)

    # Clean up any existing container first
    print("Cleaning up existing DNS container...")
    manager.stop()
    manager.remove_container()

    # Build the container
    print("Building DNS container...")
    build_result = manager.build()
    assert build_result.success, f"DNS container build failed: {build_result.stderr}"

    # Start the container on a different port for testing (port 53 is usually taken)
    print("Starting DNS container...")
    run_result = manager.run(port_mapping="5354:53")
    assert run_result.success, f"DNS container start failed: {run_result.stderr}"

    # Wait for DNS service to be ready
    print("Waiting for DNS service to start...")
    time.sleep(2)

    yield manager

    # Cleanup: keep container running for debugging if tests fail
    print("DNS container tests completed - container left running for inspection")


def run_dig_query(
    query_type: str,
    domain: str,
    server: str = "127.0.0.1",
    port: int = 5354,
    timeout: int = 2,
) -> Dict[str, Any]:
    """Run a dig query and return parsed results."""
    cmd = [
        "dig",
        f"@{server}",
        "-p",
        str(port),
        "+tcp",
        domain,
        query_type,
        "+short",
        "+time=1",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": "Query timeout",
            "returncode": -1,
        }


def test_container_startup(dns_container):
    """Test that DNS container starts successfully."""
    # If we got here, the container started successfully in the fixture
    assert True


def test_dns_port_accessible(dns_container):
    """Test that DNS port 5354 is accessible."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        # Try to connect to DNS port
        result = sock.connect_ex(("127.0.0.1", 5354))
        sock.close()
        # Connection should succeed (return 0) or be refused (connection established)
        assert result == 0, f"Cannot connect to DNS port 5354: {result}"
    except Exception as e:
        pytest.fail(f"DNS port accessibility test failed: {e}")


def test_dns_basic_resolution(dns_container):
    """Test basic DNS resolution functionality."""
    # Test resolution of a well-known domain
    result = run_dig_query("A", "google.com")
    assert result["success"], f"Basic DNS resolution failed: {result['error']}"
    assert result["output"], "No DNS response received"

    # Response should contain an IP address
    lines = result["output"].split("\n")
    assert any(
        line for line in lines if line and "." in line
    ), "No IP address in DNS response"


def test_local_zone_a_records(dns_container):
    """Test A record resolution for local zone."""
    test_cases = [
        ("ns1.local.dev", "192.168.1.10"),
        ("www.local.dev", "192.168.1.11"),
        ("mail.local.dev", "192.168.1.12"),
        ("apache.local.dev", "192.168.1.11"),
    ]

    for domain, expected_ip in test_cases:
        result = run_dig_query("A", domain)
        assert result[
            "success"
        ], f"A record query failed for {domain}: {result['error']}"
        assert (
            expected_ip in result["output"]
        ), f"Expected IP {expected_ip} not found for {domain}, got: {result['output']}"


def test_local_zone_cname_records(dns_container):
    """Test CNAME record resolution for local zone."""
    test_cases = [
        ("ftp.local.dev", "www.local.dev"),
        ("webmail.local.dev", "mail.local.dev"),
    ]

    for domain, expected_target in test_cases:
        result = run_dig_query("CNAME", domain)
        assert result["success"], f"CNAME query failed for {domain}: {result['error']}"
        assert (
            expected_target in result["output"]
        ), f"Expected CNAME {expected_target} not found for {domain}"


def test_mx_records(dns_container):
    """Test MX record resolution for mail server."""
    result = run_dig_query("MX", "local.dev")
    assert result["success"], f"MX record query failed: {result['error']}"
    assert (
        "mail.local.dev" in result["output"]
    ), f"Expected MX record not found, got: {result['output']}"
    assert "10" in result["output"], "MX priority not found in response"


def test_txt_records(dns_container):
    """Test TXT record resolution."""
    # Test SPF record
    result = run_dig_query("TXT", "local.dev")
    assert result["success"], f"TXT record query failed: {result['error']}"
    assert (
        "spf1" in result["output"].lower()
    ), f"SPF record not found, got: {result['output']}"

    # Test DMARC record
    result = run_dig_query("TXT", "_dmarc.local.dev")
    assert result["success"], f"DMARC TXT record query failed: {result['error']}"
    assert (
        "dmarc1" in result["output"].lower()
    ), f"DMARC record not found, got: {result['output']}"


def test_srv_records(dns_container):
    """Test SRV record resolution for services."""
    test_cases = [
        ("_http._tcp.local.dev", "www.local.dev"),
        ("_https._tcp.local.dev", "www.local.dev"),
        ("_smtp._tcp.local.dev", "mail.local.dev"),
        ("_imap._tcp.local.dev", "mail.local.dev"),
    ]

    for srv_record, expected_target in test_cases:
        result = run_dig_query("SRV", srv_record)
        assert result[
            "success"
        ], f"SRV query failed for {srv_record}: {result['error']}"
        assert (
            expected_target in result["output"]
        ), f"Expected SRV target {expected_target} not found for {srv_record}"


def test_reverse_dns_resolution(dns_container):
    """Test reverse DNS (PTR) record resolution."""
    test_cases = [
        ("10.0.168.192.in-addr.arpa", "ns1.local.dev"),
        ("11.0.168.192.in-addr.arpa", "www.local.dev"),
        ("12.0.168.192.in-addr.arpa", "mail.local.dev"),
    ]

    for ptr_query, expected_hostname in test_cases:
        result = run_dig_query("PTR", ptr_query)
        assert result["success"], f"PTR query failed for {ptr_query}: {result['error']}"
        assert (
            expected_hostname in result["output"]
        ), f"Expected PTR {expected_hostname} not found for {ptr_query}"


def test_dns_logging_functionality(dns_container):
    """Test that DNS server is logging queries."""
    # Make a query to generate log entries
    run_dig_query("A", "test.local.dev")

    # Check for log files in container
    log_result = dns_container.execute_command(["ls", "-la", "/var/log/bind"])
    assert log_result.success, f"Failed to access log directory: {log_result.stderr}"

    # Check for query log entries (BIND logs to syslog by default)
    # Try checking various log locations
    syslog_result = dns_container.execute_command(["ls", "-la", "/var/log/"])
    assert syslog_result.success, "Failed to access system log directory"

    # BIND should be writing to logs - check if any log files exist
    assert (
        "bind" in syslog_result.stdout or "syslog" in syslog_result.stdout
    ), "No DNS log files found"


def test_zone_file_validation(dns_container):
    """Test that zone files are syntactically correct."""
    # Validate forward zone file
    forward_result = dns_container.execute_command(
        ["named-checkzone", "local.dev", "/etc/bind/zones/db.local.zone"]
    )
    assert (
        forward_result.success
    ), f"Forward zone validation failed: {forward_result.stderr}"
    assert (
        "OK" in forward_result.stdout
    ), "Forward zone file validation did not return OK"

    # Validate reverse zone file
    reverse_result = dns_container.execute_command(
        ["named-checkzone", "0.168.192.in-addr.arpa", "/etc/bind/zones/db.local.rev"]
    )
    assert (
        reverse_result.success
    ), f"Reverse zone validation failed: {reverse_result.stderr}"
    assert (
        "OK" in reverse_result.stdout
    ), "Reverse zone file validation did not return OK"


def test_configuration_validation(dns_container):
    """Test that BIND configuration is valid."""
    # Validate main BIND configuration
    config_result = dns_container.execute_command(["named-checkconf"])
    assert (
        config_result.success
    ), f"BIND configuration validation failed: {config_result.stderr}"

    # If there are warnings, they should not be critical errors
    if config_result.stderr:
        # Some warnings might be acceptable, but errors are not
        assert (
            "error" not in config_result.stderr.lower()
        ), f"Configuration errors found: {config_result.stderr}"


def test_container_logs_accessible(dns_container):
    """Test that container logs are accessible and contain startup messages."""
    logs_result = dns_container.logs()
    assert logs_result.success, "Failed to retrieve container logs"
    assert (
        "Starting DNS server" in logs_result.stdout
    ), "DNS startup message not found in logs"
    assert (
        "BIND DNS server" in logs_result.stdout
    ), "BIND startup message not found in logs"
