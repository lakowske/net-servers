"""Container management with Podman."""

import logging
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class VolumeMount:
    """Configuration for volume mounting."""

    host_path: str
    container_path: str
    read_only: bool = False

    def to_podman_arg(self) -> str:
        """Convert to podman volume argument format."""
        if self.read_only:
            return f"{self.host_path}:{self.container_path}:ro"  # noqa: E231
        return f"{self.host_path}:{self.container_path}"  # noqa: E231


@dataclass
class ContainerResult:
    """Result of a container operation."""

    success: bool
    stdout: str
    stderr: str
    return_code: int


@dataclass
class ContainerConfig:
    """Configuration for container operations."""

    image_name: str
    dockerfile: str = "Dockerfile"
    port: int = 8080
    container_name: str = ""
    volumes: List[VolumeMount] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    config_templates: Dict[str, str] = field(default_factory=dict)
    state_paths: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Auto-generate container name if not provided."""
        if not self.container_name:
            # Convert image name to container name (remove registry/org prefixes)
            self.container_name = self.image_name.split("/")[-1].replace(":", "-")


class ContainerManager:
    """Manages container operations using Podman."""

    def __init__(self, config: ContainerConfig) -> None:
        """Initialize container manager with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)

    def _run_command(self, cmd: List[str]) -> ContainerResult:
        """Execute podman command and return structured result."""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5 minutes timeout
            )

            return ContainerResult(
                success=result.returncode == 0,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                return_code=result.returncode,
            )

        except subprocess.TimeoutExpired:
            return ContainerResult(
                success=False,
                stdout="",
                stderr="Command timed out after 5 minutes",
                return_code=-1,
            )
        except Exception as e:
            return ContainerResult(
                success=False,
                stdout="",
                stderr=f"Unexpected error: {str(e)}",
                return_code=-1,
            )

    def build(self, rebuild: bool = False) -> ContainerResult:
        """Build container image with full logging."""
        cmd = ["podman", "build", "-t", self.config.image_name]

        if rebuild:
            cmd.append("--no-cache")

        cmd.extend(["-f", self.config.dockerfile, "."])

        self.logger.info(
            f"Building image {self.config.image_name} from {self.config.dockerfile}"
        )
        result = self._run_command(cmd)

        if result.success:
            self.logger.info(f"Successfully built image {self.config.image_name}")
        else:
            self.logger.error(
                f"Failed to build image {self.config.image_name}: {result.stderr}"
            )

        return result

    def run(
        self, detached: bool = True, port_mapping: Optional[str] = None
    ) -> ContainerResult:
        """Run container, return container ID in stdout."""
        cmd = ["podman", "run"]

        if detached:
            cmd.append("-d")

        # Use provided port mapping or default based on container type
        if port_mapping:
            cmd.extend(["-p", port_mapping])
        else:
            # Default port mappings based on service type
            if "apache" in self.config.image_name:
                port_mapping = f"{self.config.port}" + ":80"
                cmd.extend(["-p", port_mapping])
            elif "mail" in self.config.image_name:
                # Map multiple ports for mail service
                cmd.extend(["-p", "25:25"])  # SMTP
                cmd.extend(["-p", "143:143"])  # IMAP
                cmd.extend(["-p", "110:110"])  # POP3
                cmd.extend(["-p", "993:993"])  # IMAPS
                cmd.extend(["-p", "995:995"])  # POP3S
                cmd.extend(["-p", "587:587"])  # SMTP submission
            elif "dns" in self.config.image_name:
                port_mapping = f"{self.config.port}" + ":53"
                cmd.extend(["-p", port_mapping])
            else:
                # Generic fallback
                port_mapping = f"{self.config.port}" + ":80"
                cmd.extend(["-p", port_mapping])

        # Add volume mounts
        for volume in self.config.volumes:
            cmd.extend(["-v", volume.to_podman_arg()])

        # Add environment variables
        for key, value in self.config.environment.items():
            cmd.extend(["-e", f"{key}={value}"])

        cmd.extend(["--name", self.config.container_name, self.config.image_name])

        self.logger.info(
            f"Running container {self.config.container_name} "
            f"from {self.config.image_name}"
        )
        result = self._run_command(cmd)

        if result.success:
            self.logger.info(
                f"Successfully started container {self.config.container_name}"
            )
        else:
            self.logger.error(
                f"Failed to start container {self.config.container_name}: "
                f"{result.stderr}"
            )

        return result

    def stop(self) -> ContainerResult:
        """Stop running container."""
        cmd = ["podman", "stop", self.config.container_name]

        self.logger.info(f"Stopping container {self.config.container_name}")
        result = self._run_command(cmd)

        if result.success:
            self.logger.info(
                f"Successfully stopped container {self.config.container_name}"
            )
        else:
            self.logger.warning(
                f"Failed to stop container {self.config.container_name}: "
                f"{result.stderr}"
            )

        return result

    def remove_container(self, force: bool = False) -> ContainerResult:
        """Remove container."""
        cmd = ["podman", "rm"]

        if force:
            cmd.append("-f")

        cmd.append(self.config.container_name)

        self.logger.info(f"Removing container {self.config.container_name}")
        result = self._run_command(cmd)

        if result.success:
            self.logger.info(
                f"Successfully removed container {self.config.container_name}"
            )
        else:
            self.logger.warning(
                f"Failed to remove container {self.config.container_name}: "
                f"{result.stderr}"
            )

        return result

    def remove_image(self, force: bool = False) -> ContainerResult:
        """Remove container image."""
        cmd = ["podman", "rmi"]

        if force:
            cmd.append("-f")

        cmd.append(self.config.image_name)

        self.logger.info(f"Removing image {self.config.image_name}")
        result = self._run_command(cmd)

        if result.success:
            self.logger.info(f"Successfully removed image {self.config.image_name}")
        else:
            self.logger.warning(
                f"Failed to remove image {self.config.image_name}: {result.stderr}"
            )

        return result

    def list_containers(self, all_containers: bool = False) -> ContainerResult:
        """List containers."""
        cmd = ["podman", "ps", "--format", "json"]

        if all_containers:
            cmd.append("-a")

        result = self._run_command(cmd)
        return result

    def logs(self, follow: bool = False, tail: Optional[int] = None) -> ContainerResult:
        """Get container logs."""
        cmd = ["podman", "logs"]

        if follow:
            cmd.append("-f")

        if tail is not None:
            cmd.extend(["--tail", str(tail)])

        cmd.append(self.config.container_name)

        result = self._run_command(cmd)
        return result

    def inspect(self) -> ContainerResult:
        """Inspect container details."""
        cmd = ["podman", "inspect", self.config.container_name]
        result = self._run_command(cmd)
        return result

    def execute_command(self, command: List[str]) -> ContainerResult:
        """Execute a command inside the running container."""
        cmd = ["podman", "exec", self.config.container_name] + command

        self.logger.debug(
            f"Executing command in container {self.config.container_name}: "
            f"{' '.join(command)}"
        )
        result = self._run_command(cmd)

        if not result.success:
            self.logger.warning(
                f"Command failed in container {self.config.container_name}: "
                f"{result.stderr}"
            )

        return result
