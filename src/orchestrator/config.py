"""Configuration loader for orchestrator."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class OrchestratorSettings(BaseModel):
    """Orchestrator settings."""

    model_config = ConfigDict(frozen=True)

    num_branches: int = Field(default=3, ge=1, le=3)
    max_iterations: int = Field(default=5, ge=1)
    early_stop_threshold: int = Field(default=2, ge=1)


class BudgetSettings(BaseModel):
    """Budget settings."""

    model_config = ConfigDict(frozen=True)

    max_cost_usd: float = Field(default=10.0, gt=0)
    max_time_hours: float = Field(default=1.0, gt=0)
    max_time_seconds: float | None = Field(default=None, gt=0)  # Alternative to max_time_hours
    max_tokens_per_branch: int = Field(default=50000, gt=0)

    def get_max_time_seconds(self) -> float:
        """Get max time in seconds, preferring max_time_seconds if set."""
        if self.max_time_seconds is not None:
            return self.max_time_seconds
        return self.max_time_hours * 3600


class DockerSettings(BaseModel):
    """Docker settings."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    image: str = "python:3.11-slim"
    mem_limit: str = "2g"
    cpu_quota: int = 100000
    network_disabled: bool = True


class MemorySettings(BaseModel):
    """Memory settings."""

    model_config = ConfigDict(frozen=True)

    embedding_model: str = "all-MiniLM-L6-v2"
    top_k: int = Field(default=5, ge=1)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class LoggingSettings(BaseModel):
    """Logging settings."""

    model_config = ConfigDict(frozen=True)

    level: str = "INFO"
    format: str = "json"


class OrchestratorConfig(BaseModel):
    """Complete orchestrator configuration."""

    model_config = ConfigDict(frozen=True)

    orchestrator: OrchestratorSettings
    budget: BudgetSettings
    docker: DockerSettings
    memory: MemorySettings
    logging: LoggingSettings

    @classmethod
    def from_yaml(cls, path: Path | str) -> "OrchestratorConfig":
        """Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            OrchestratorConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(**data)

    @classmethod
    def default(cls) -> "OrchestratorConfig":
        """Create default configuration.

        Returns:
            OrchestratorConfig with default values
        """
        return cls(
            orchestrator=OrchestratorSettings(),
            budget=BudgetSettings(),
            docker=DockerSettings(),
            memory=MemorySettings(),
            logging=LoggingSettings(),
        )
