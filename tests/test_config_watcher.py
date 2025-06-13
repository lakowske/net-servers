"""Unit tests for configuration watcher daemon."""

import tempfile
from unittest.mock import MagicMock, patch

from net_servers.config.manager import ConfigurationManager


class TestConfigurationWatcher:
    """Test configuration watcher functionality."""

    def test_watcher_module_imports(self):
        """Test that watcher module can be imported."""
        from net_servers.config import watcher

        # Test basic imports work
        assert hasattr(watcher, "ConfigurationWatcher")
        assert hasattr(watcher, "ConfigurationDaemon")

    def test_configuration_daemon_basic_init(self):
        """Test configuration daemon basic initialization."""
        from net_servers.config.watcher import ConfigurationDaemon

        # Test with minimal arguments
        daemon = ConfigurationDaemon("/tmp/test")

        assert daemon.base_path == "/tmp/test"

    @patch("net_servers.config.watcher.Observer")
    def test_configuration_daemon_run_startup(self, mock_observer_class):
        """Test configuration daemon run startup."""
        from net_servers.config.watcher import ConfigurationDaemon

        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer

        with tempfile.TemporaryDirectory() as temp_dir:
            daemon = ConfigurationDaemon(temp_dir)

            # Mock the infinite loop to stop after setup
            with patch("time.sleep", side_effect=KeyboardInterrupt):
                try:
                    daemon.run()
                except KeyboardInterrupt:
                    pass

            # Should have started observer
            mock_observer.start.assert_called()

    def test_configuration_daemon_with_debounce(self):
        """Test configuration daemon with debounce parameter."""
        from net_servers.config.watcher import ConfigurationDaemon

        with tempfile.TemporaryDirectory() as temp_dir:
            daemon = ConfigurationDaemon(temp_dir, 2.0)

            # Should create daemon with custom debounce
            assert daemon.base_path == temp_dir
            assert daemon.debounce_delay == 2.0

    def test_configuration_watcher_basic_creation(self):
        """Test configuration watcher basic creation."""
        from net_servers.config.watcher import ConfigurationWatcher

        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigurationManager(base_path=temp_dir)
            sync_manager = MagicMock()

            # Test that watcher can be created
            watcher = ConfigurationWatcher(
                sync_manager, config_manager.paths.config_path
            )

            # Basic functionality test
            assert watcher is not None

    def test_basic_file_system_watching(self):
        """Test basic file system watching setup."""
        from net_servers.config.watcher import ConfigurationWatcher

        with tempfile.TemporaryDirectory():
            sync_manager = MagicMock()

            # Test watcher creation - ConfigurationWatcher constructor
            # just takes sync_manager and debounce_delay
            watcher = ConfigurationWatcher(sync_manager)

            # Test basic properties
            assert hasattr(watcher, "sync_manager")
            assert hasattr(watcher, "observer")
