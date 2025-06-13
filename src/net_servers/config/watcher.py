"""Configuration file watcher for automatic synchronization."""

import logging
import time
from pathlib import Path
from threading import Event, Thread, Timer
from typing import Dict, Optional, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .manager import ConfigurationManager
from .sync import ConfigurationSyncManager


class ConfigurationFileHandler(FileSystemEventHandler):
    """Handles configuration file change events."""

    def __init__(
        self, sync_manager: ConfigurationSyncManager, debounce_delay: float = 2.0
    ):
        """Initialize the file handler."""
        super().__init__()
        self.sync_manager = sync_manager
        self.debounce_delay = debounce_delay
        self.logger = logging.getLogger(__name__)

        # Debouncing to avoid multiple rapid changes
        self._pending_changes: Set[str] = set()
        self._debounce_timer: Dict[str, Timer] = {}

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(str(event.src_path))

        # Only handle YAML configuration files
        if file_path.suffix.lower() not in [".yaml", ".yml"]:
            return

        self.logger.info(f"Configuration file changed: {file_path}")
        self._schedule_sync(str(file_path))

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        self.on_modified(event)

    def _schedule_sync(self, file_path: str) -> None:
        """Schedule a debounced sync operation."""
        # Cancel existing timer for this file
        if file_path in self._debounce_timer:
            self._debounce_timer[file_path].cancel()

        # Schedule new sync
        timer = Timer(self.debounce_delay, self._debounced_sync, args=(file_path,))
        self._debounce_timer[file_path] = timer
        timer.start()

    def _debounced_sync(self, file_path: str) -> None:
        """Execute sync after debounce delay."""
        # Timer already handled the delay

        try:
            file_name = Path(file_path).name

            # Reload configuration
            self.sync_manager.config_manager.reload_config()

            if file_name in ["users.yaml", "global.yaml"]:
                self.logger.info("Syncing users due to configuration change")
                if self.sync_manager.sync_all_users():
                    self.logger.info("✓ Users synchronized successfully")
                else:
                    self.logger.error("✗ Failed to sync users")

            if file_name in ["domains.yaml", "global.yaml"]:
                self.logger.info("Syncing domains due to configuration change")
                if self.sync_manager.sync_all_domains():
                    self.logger.info("✓ Domains synchronized successfully")
                else:
                    self.logger.error("✗ Failed to sync domains")

            if file_name.startswith("services"):
                self.logger.info(
                    "Reloading services due to service configuration change"
                )
                if self.sync_manager.reload_all_services():
                    self.logger.info("✓ Services reloaded successfully")
                else:
                    self.logger.warning("⚠ Some services failed to reload")

            # Validate configuration after changes
            validation_results = self.sync_manager.validate_all_services()
            for service, errors in validation_results.items():
                if errors:
                    self.logger.warning(f"Validation issues in {service}: {errors}")

        except Exception as e:
            self.logger.error(f"Error during configuration sync: {e}")

        finally:
            # Clean up timer reference
            if file_path in self._debounce_timer:
                del self._debounce_timer[file_path]


class ConfigurationWatcher:
    """Watches configuration files and automatically synchronizes changes."""

    def __init__(
        self, sync_manager: ConfigurationSyncManager, debounce_delay: float = 2.0
    ):
        """Initialize the configuration watcher."""
        self.sync_manager = sync_manager
        self.debounce_delay = debounce_delay
        self.logger = logging.getLogger(__name__)

        self.observer = Observer()
        self.handler = ConfigurationFileHandler(sync_manager, debounce_delay)
        self._stop_event = Event()
        self._watch_thread: Optional[Thread] = None

    def start(self) -> None:
        """Start watching configuration files."""
        config_path = self.sync_manager.config_manager.paths.config_path

        if not config_path.exists():
            self.logger.warning(f"Configuration path does not exist: {config_path}")
            return

        self.logger.info(f"Starting configuration file watcher on: {config_path}")

        # Watch the configuration directory recursively
        self.observer.schedule(self.handler, str(config_path), recursive=True)
        self.observer.start()

        # Start the monitoring thread
        self._watch_thread = Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

        self.logger.info("Configuration watcher started")

    def stop(self) -> None:
        """Stop watching configuration files."""
        self.logger.info("Stopping configuration watcher")

        self._stop_event.set()

        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=5)

        self.logger.info("Configuration watcher stopped")

    def _watch_loop(self) -> None:
        """Main watching loop."""
        try:
            while not self._stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Configuration watcher interrupted")
        except Exception as e:
            self.logger.error(f"Error in configuration watcher: {e}")

    def __enter__(self) -> "ConfigurationWatcher":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[object],
    ) -> None:
        """Context manager exit."""
        self.stop()


class ConfigurationDaemon:
    """Daemon that runs configuration watcher and keeps services synchronized."""

    def __init__(self, base_path: str = "/data", debounce_delay: float = 2.0):
        """Initialize the configuration daemon."""
        self.base_path = base_path
        self.debounce_delay = debounce_delay
        self.logger = logging.getLogger(__name__)

        # Will be initialized when started
        self.config_manager: Optional[ConfigurationManager] = None
        self.sync_manager: Optional[ConfigurationSyncManager] = None
        self.watcher: Optional[ConfigurationWatcher] = None
        self._stop_event = Event()

    def initialize(self) -> bool:
        """Initialize the daemon components."""
        try:
            self.logger.info("Initializing configuration daemon")

            # Initialize configuration manager
            self.config_manager = ConfigurationManager(self.base_path)

            # Initialize sync manager
            from ..actions.container import ContainerManager
            from ..config.containers import get_container_config
            from .sync import (
                ConfigurationSyncManager,
                DnsServiceSynchronizer,
                MailServiceSynchronizer,
            )

            self.sync_manager = ConfigurationSyncManager(self.config_manager)

            # Register synchronizers for running containers
            try:
                # Mail service
                mail_config = get_container_config("mail", use_config_manager=True)
                mail_container = ContainerManager(mail_config)
                mail_sync = MailServiceSynchronizer(self.config_manager, mail_container)
                self.sync_manager.register_synchronizer("mail", mail_sync)

                # DNS service
                dns_config = get_container_config("dns", use_config_manager=True)
                dns_container = ContainerManager(dns_config)
                dns_sync = DnsServiceSynchronizer(self.config_manager, dns_container)
                self.sync_manager.register_synchronizer("dns", dns_sync)

                self.logger.info("Service synchronizers registered")

            except Exception as e:
                self.logger.warning(f"Could not register all synchronizers: {e}")

            # Initialize watcher
            self.watcher = ConfigurationWatcher(self.sync_manager, self.debounce_delay)

            self.logger.info("Configuration daemon initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize configuration daemon: {e}")
            return False

    def start(self) -> None:
        """Start the configuration daemon."""
        if not self.initialize():
            raise RuntimeError("Failed to initialize configuration daemon")

        self.logger.info("Starting configuration daemon")

        # Perform initial sync
        self.logger.info("Performing initial configuration sync")
        if self.sync_manager and self.sync_manager.sync_all_users():
            self.logger.info("✓ Initial user sync completed")
        else:
            self.logger.warning("⚠ Initial user sync had issues")

        if self.sync_manager and self.sync_manager.sync_all_domains():
            self.logger.info("✓ Initial domain sync completed")
        else:
            self.logger.warning("⚠ Initial domain sync had issues")

        # Start file watcher
        if self.watcher:
            self.watcher.start()

        self.logger.info("Configuration daemon started - watching for changes")

    def stop(self) -> None:
        """Stop the configuration daemon."""
        self.logger.info("Stopping configuration daemon")

        self._stop_event.set()

        if self.watcher:
            self.watcher.stop()

        self.logger.info("Configuration daemon stopped")

    def run(self) -> None:
        """Run the daemon (blocking)."""
        try:
            self.start()

            # Keep running until stopped
            while not self._stop_event.is_set():
                time.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("Configuration daemon interrupted by user")
        except Exception as e:
            self.logger.error(f"Configuration daemon error: {e}")
        finally:
            self.stop()

    def __enter__(self) -> "ConfigurationDaemon":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[object],
    ) -> None:
        """Context manager exit."""
        self.stop()
