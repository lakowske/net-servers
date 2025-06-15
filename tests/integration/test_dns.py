"""Integration tests for DNS server container."""

import socket
import subprocess
import time
from typing import Any, Dict

import pytest

from .port_manager import get_port_manager


@pytest.fixture(scope="session")
def dns_container(podman_available: bool):
    """Session-scoped fixture for DNS container testing.

    Container is started once per test session and reused across all tests.
    Container is left running after tests for debugging and performance.
    """
    if not podman_available:
        pytest.skip("Podman not available for integration testing")

    from .conftest import ContainerTestHelper

    helper = ContainerTestHelper("dns")

    # Build container if needed (only done once)
    if not helper.manager.image_exists():
        print("Building DNS container...")
        build_result = helper.manager.build()
        assert (
            build_result.success
        ), f"DNS container build failed: {build_result.stderr}"

    # Start container, reusing if already running
    if not helper.start_container(force_restart=False):
        pytest.fail("Failed to start DNS container")

    # Brief wait for DNS service only if container was just started
    if not helper.is_container_ready():
        print("Waiting for DNS service to initialize...")
        time.sleep(2)

    try:
        yield helper
        # Print debugging info when tests complete
        helper.print_container_info()
        print(
            "\nDNS container left running for debugging and performance. "
            "Rerun tests to reuse existing container."
        )
    except Exception:
        # On test failures, keep container for debugging
        helper.print_container_info()
        print("\nDNS container left running for debugging failed tests.")
        raise
    # Note: Container is intentionally NOT stopped to allow log inspection and reuse


def run_dig_query(
    query_type: str,
    domain: str,
    server: str = "127.0.0.1",
    port: int = None,
    timeout: int = 2,
    dns_container=None,
) -> Dict[str, Any]:
    """Run a dig query and return parsed results."""
    # Get the DNS port from the port manager if not provided
    if port is None:
        if dns_container:
            # Use the container helper to get the correct port
            port = dns_container.get_container_port(53)
        else:
            try:
                port = get_port_manager().get_host_port("dns", 53)
            except KeyError:
                port = 5454  # Fallback to actual testing port

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
    """Test that DNS port is accessible."""
    # Use container helper to get the correct port
    dns_port = dns_container.get_container_port(53)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        # Try to connect to DNS port
        result = sock.connect_ex(("127.0.0.1", dns_port))
        sock.close()
        # Connection should succeed (return 0) or be refused (connection established)
        assert result == 0, f"Cannot connect to DNS port {dns_port}: {result}"
    except Exception as e:
        pytest.fail(f"DNS port accessibility test failed: {e}")


def test_dns_basic_resolution(dns_container):
    """Test basic DNS resolution functionality."""
    # Test resolution of a well-known domain using container's port mapping
    result = run_dig_query("A", "google.com", dns_container=dns_container)
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
        result = run_dig_query("A", domain, dns_container=dns_container)
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
        result = run_dig_query("CNAME", domain, dns_container=dns_container)
        assert result["success"], f"CNAME query failed for {domain}: {result['error']}"
        assert (
            expected_target in result["output"]
        ), f"Expected CNAME {expected_target} not found for {domain}"


def test_mx_records(dns_container):
    """Test MX record resolution for mail server."""
    result = run_dig_query("MX", "local.dev", dns_container=dns_container)
    assert result["success"], f"MX record query failed: {result['error']}"
    assert (
        "mail.local.dev" in result["output"]
    ), f"Expected MX record not found, got: {result['output']}"
    assert "10" in result["output"], "MX priority not found in response"


def test_txt_records(dns_container):
    """Test TXT record resolution."""
    # Test SPF record
    result = run_dig_query("TXT", "local.dev", dns_container=dns_container)
    assert result["success"], f"TXT record query failed: {result['error']}"
    assert (
        "spf1" in result["output"].lower()
    ), f"SPF record not found, got: {result['output']}"

    # Test DMARC record
    result = run_dig_query("TXT", "_dmarc.local.dev", dns_container=dns_container)
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
        result = run_dig_query("SRV", srv_record, dns_container=dns_container)
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
        result = run_dig_query("PTR", ptr_query, dns_container=dns_container)
        assert result["success"], f"PTR query failed for {ptr_query}: {result['error']}"
        assert (
            expected_hostname in result["output"]
        ), f"Expected PTR {expected_hostname} not found for {ptr_query}"


def test_dns_logging_functionality(dns_container):
    """Test that DNS server is logging queries."""
    # Make a query to generate log entries
    run_dig_query("A", "test.local.dev", dns_container=dns_container)

    # Check for log files in container
    log_result = dns_container.exec_command(["ls", "-la", "/var/log/bind"])
    assert (
        log_result.returncode == 0
    ), f"Failed to access log directory: {log_result.stderr}"

    # Check for query log entries (BIND logs to syslog by default)
    # Try checking various log locations
    syslog_result = dns_container.exec_command(["ls", "-la", "/var/log/"])
    assert syslog_result.returncode == 0, "Failed to access system log directory"

    # BIND should be writing to logs - check if any log files exist
    assert (
        "bind" in syslog_result.stdout or "syslog" in syslog_result.stdout
    ), "No DNS log files found"


def test_zone_file_validation(dns_container):
    """Test that zone files are syntactically correct."""
    # Validate forward zone file
    forward_result = dns_container.exec_command(
        ["named-checkzone", "local.dev", "/etc/bind/zones/db.local.zone"]
    )
    assert (
        forward_result.returncode == 0
    ), f"Forward zone validation failed: {forward_result.stderr}"
    assert (
        "OK" in forward_result.stdout
    ), "Forward zone file validation did not return OK"

    # Validate reverse zone file
    reverse_result = dns_container.exec_command(
        ["named-checkzone", "0.168.192.in-addr.arpa", "/etc/bind/zones/db.local.rev"]
    )
    assert (
        reverse_result.returncode == 0
    ), f"Reverse zone validation failed: {reverse_result.stderr}"
    assert (
        "OK" in reverse_result.stdout
    ), "Reverse zone file validation did not return OK"


def test_configuration_validation(dns_container):
    """Test that BIND configuration is valid."""
    # Validate main BIND configuration
    config_result = dns_container.exec_command(["named-checkconf"])
    assert (
        config_result.returncode == 0
    ), f"BIND configuration validation failed: {config_result.stderr}"

    # If there are warnings, they should not be critical errors
    if config_result.stderr:
        # Some warnings might be acceptable, but errors are not
        assert (
            "error" not in config_result.stderr.lower()
        ), f"Configuration errors found: {config_result.stderr}"


def test_container_logs_accessible(dns_container):
    """Test that container logs are accessible and contain startup messages."""
    logs_result = subprocess.run(
        ["podman", "logs", dns_container.config.container_name],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert logs_result.returncode == 0, "Failed to retrieve container logs"
    assert (
        "Starting DNS server" in logs_result.stdout
    ), "DNS startup message not found in logs"
    assert (
        "BIND DNS server" in logs_result.stdout
    ), "BIND startup message not found in logs"
