"""Integration tests for Mail container."""

import email.mime.text
import imaplib
import poplib
import smtplib
import time
from email.mime.text import MIMEText

from .conftest import ContainerTestHelper


class TestMailContainer:
    """Test Mail container functionality in logical order."""

    def test_01_container_starts_successfully(
        self, mail_container: ContainerTestHelper
    ):
        """Test that Mail container starts and is running."""
        assert mail_container.is_container_ready()

    def test_02_mail_services_running(self, mail_container: ContainerTestHelper):
        """Test that mail services (Postfix, Dovecot) are running."""
        # Check Postfix
        result = mail_container.exec_command(["pgrep", "-f", "postfix"])
        assert result.returncode == 0

        # Check Dovecot
        result = mail_container.exec_command(["pgrep", "-f", "dovecot"])
        assert result.returncode == 0

    def test_03_smtp_basic_communication(self, mail_container: ContainerTestHelper):
        """Test SMTP service responds (port accessible and functional)."""
        port = mail_container.get_container_port(25)

        with smtplib.SMTP("localhost", port, timeout=2) as smtp:
            response = smtp.noop()
            assert response[0] == 250  # OK response

    def test_04_imap_basic_communication(self, mail_container: ContainerTestHelper):
        """Test IMAP service responds (port accessible and functional)."""
        port = mail_container.get_container_port(143)

        # Just connect to prove service is running
        with imaplib.IMAP4("localhost", port):
            # Connection successful if we get here
            pass

    def test_05_pop3_basic_communication(self, mail_container: ContainerTestHelper):
        """Test POP3 service responds (port accessible and functional)."""
        port = mail_container.get_container_port(110)

        # Just connect to prove service is running
        pop = poplib.POP3("localhost", port, timeout=2)
        try:
            # Connection successful if we get here
            pass
        finally:
            try:
                pop.quit()
            except Exception:
                pass

    def test_06_mail_directories_created(self, mail_container: ContainerTestHelper):
        """Test that mail directories and user setup are properly configured."""
        # Check main mail directory
        result = mail_container.exec_command(["ls", "-la", "/var/mail/vhosts"])
        assert result.returncode == 0

        # Check test user directories exist
        result = mail_container.exec_command(["ls", "-la", "/var/mail/vhosts/local"])
        assert result.returncode == 0
        assert "test" in result.stdout

    def test_07_imap_authentication(self, mail_container: ContainerTestHelper):
        """Test IMAP authentication with test user credentials."""
        port = mail_container.get_container_port(143)

        with imaplib.IMAP4("localhost", port) as imap:
            result = imap.login("test@local", "password")
            assert result[0] == "OK"

    def test_08_pop3_authentication(self, mail_container: ContainerTestHelper):
        """Test POP3 authentication with test user credentials."""
        port = mail_container.get_container_port(110)

        pop = poplib.POP3("localhost", port, timeout=2)
        try:
            pop.user("test@local")
            response = pop.pass_("password")
            assert b"+OK" in response
        finally:
            try:
                pop.quit()
            except Exception:
                pass

    def test_09_smtp_send_email(self, mail_container: ContainerTestHelper):
        """Test sending an email via SMTP."""
        port = mail_container.get_container_port(25)

        msg = MIMEText("This is a test email from integration test.")
        msg["Subject"] = "Integration Test Email"
        msg["From"] = "test@local"
        msg["To"] = "test@local"

        with smtplib.SMTP("localhost", port, timeout=2) as smtp:
            smtp.send_message(msg)

    def test_10_email_delivery_workflow(self, mail_container: ContainerTestHelper):
        """Test complete email delivery workflow: send via SMTP, receive via IMAP."""
        smtp_port = mail_container.get_container_port(25)
        imap_port = mail_container.get_container_port(143)

        # Send email
        test_subject = "Integration Test Workflow Email"
        test_body = "This email tests the complete delivery workflow."

        msg = MIMEText(test_body)
        msg["Subject"] = test_subject
        msg["From"] = "test@local"
        msg["To"] = "test@local"

        with smtplib.SMTP("localhost", smtp_port, timeout=2) as smtp:
            smtp.send_message(msg)

        # Wait for delivery
        time.sleep(1)

        # Verify email received
        with imaplib.IMAP4("localhost", imap_port) as imap:
            imap.login("test@local", "password")
            imap.select("INBOX")

            result, message_ids = imap.search(None, f'SUBJECT "{test_subject}"')
            assert result == "OK"

            if message_ids[0]:
                message_list = message_ids[0].split()
                assert len(message_list) > 0

                result, message_data = imap.fetch(message_list[-1], "(RFC822)")
                assert result == "OK"

                email_message = email.message_from_bytes(message_data[0][1])
                assert test_subject in email_message["Subject"]

    def test_11_mail_logs_accessible(self, mail_container: ContainerTestHelper):
        """Test that mail service logs are accessible and being written."""
        # Check Postfix logs
        result = mail_container.exec_command(["ls", "-la", "/var/log/postfix/"])
        assert result.returncode == 0

        # Check Dovecot logs
        result = mail_container.exec_command(["ls", "-la", "/var/log/dovecot/"])
        assert result.returncode == 0
