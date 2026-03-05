"""Configuration management for AI-Scientist integration."""

import os
from pathlib import Path
from typing import Any

import yaml


class AIScientistConfig:
    """Configuration manager for AI-Scientist integration.

    Priority: Environment variables > Config file > Defaults
    """

    # Default configuration
    DEFAULTS = {
        "runtime": {
            "path": "external/ai-scientist-runtime",
            "launch_script": "launch_scientist.py",
        },
        "jobs": {
            "max_concurrent": 2,
            "poll_interval": 60,
            "timeout": 86400,
            "auto_start_pending": True,
        },
        "models": {
            "default": "deepseek-chat",
            "alternatives": [
                "ollama/qwen3",
                "gpt-4",
                "claude-3-5-sonnet-20241022",
            ],
        },
        "templates": {
            "default": "ai_toy_research_cn",
            "generic": "generic_ai_research_cn",
            "num_ideas": 2,
            "writeup": "md",
        },
        "ollama": {
            "host": "localhost",
            "port": 11434,
            "default_model": "qwen3",
        },
        "validation": {
            "check_ollama": True,
            "check_model": True,
            "strict": False,
        },
        "logging": {
            "level": "INFO",
            "log_path": "runs/{run_id}/external/logs/{job_id}.log",
        },
    }

    # Environment variable mappings
    ENV_MAPPINGS = {
        "AISCI_AI_SCIENTIST_PATH": ("runtime", "path"),
        "AISCI_MAX_CONCURRENT_JOBS": ("jobs", "max_concurrent"),
        "AISCI_JOB_POLL_INTERVAL": ("jobs", "poll_interval"),
        "AISCI_JOB_TIMEOUT": ("jobs", "timeout"),
        "AISCI_AUTO_START_PENDING": ("jobs", "auto_start_pending"),
        "AISCI_DEFAULT_MODEL": ("models", "default"),
        "AISCI_NUM_IDEAS": ("templates", "num_ideas"),
        "AISCI_WRITEUP_FORMAT": ("templates", "writeup"),
        "OLLAMA_HOST": ("ollama", "host"),
        "OLLAMA_PORT": ("ollama", "port"),
        "OLLAMA_MODEL": ("ollama", "default_model"),
    }

    def __init__(self, config_path: str | Path | None = None):
        """Initialize configuration manager.

        Args:
            config_path: Path to config file (default: configs/ai_scientist.yaml)
        """
        self.config_path = Path(config_path) if config_path else Path("configs/ai_scientist.yaml")
        self._config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration with priority: env vars > file > defaults."""
        # Start with defaults
        config = self._deep_copy(self.DEFAULTS)

        # Load from file if exists
        if self.config_path.exists():
            try:
                file_config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
                if file_config:
                    config = self._deep_merge(config, file_config)
            except Exception as e:
                # Fallback to defaults on error
                print(f"Warning: Failed to load config from {self.config_path}: {e}")

        # Override with environment variables
        config = self._apply_env_overrides(config)

        return config

    def _deep_copy(self, obj: Any) -> Any:
        """Deep copy a nested dict/list structure."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dicts, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _apply_env_overrides(self, config: dict) -> dict:
        """Apply environment variable overrides."""
        for env_var, (section, key) in self.ENV_MAPPINGS.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Type conversion
                if key in ["max_concurrent", "poll_interval", "timeout", "num_ideas", "port"]:
                    value = int(value)
                elif key == "auto_start_pending":
                    value = value.lower() in ("true", "1", "yes")

                # Set value
                if section in config:
                    config[section][key] = value

        return config

    def get(self, section: str, key: str | None = None, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            section: Configuration section (e.g., "jobs", "models")
            key: Configuration key within section (optional)
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        if section not in self._config:
            return default

        if key is None:
            return self._config[section]

        return self._config[section].get(key, default)

    def get_runtime_path(self) -> Path:
        """Get AI-Scientist runtime path."""
        return Path(self.get("runtime", "path"))

    def get_max_concurrent(self) -> int:
        """Get maximum concurrent jobs."""
        return self.get("jobs", "max_concurrent")

    def get_poll_interval(self) -> int:
        """Get job polling interval in seconds."""
        return self.get("jobs", "poll_interval")

    def get_timeout(self) -> int:
        """Get job timeout in seconds."""
        return self.get("jobs", "timeout")

    def get_auto_start_pending(self) -> bool:
        """Get auto-start pending jobs flag."""
        return self.get("jobs", "auto_start_pending")

    def get_default_model(self) -> str:
        """Get default model."""
        return self.get("models", "default")

    def get_num_ideas(self) -> int:
        """Get default number of ideas."""
        return self.get("templates", "num_ideas")

    def get_writeup_format(self) -> str:
        """Get default writeup format."""
        return self.get("templates", "writeup")

    def get_ollama_host(self) -> str:
        """Get Ollama service host."""
        return self.get("ollama", "host")

    def get_ollama_port(self) -> int:
        """Get Ollama service port."""
        return self.get("ollama", "port")

    def get_ollama_model(self) -> str:
        """Get default Ollama model."""
        return self.get("ollama", "default_model")

    def should_check_ollama(self) -> bool:
        """Check if Ollama validation is enabled."""
        return self.get("validation", "check_ollama")

    def should_check_model(self) -> bool:
        """Check if model validation is enabled."""
        return self.get("validation", "check_model")

    def is_strict_validation(self) -> bool:
        """Check if strict validation is enabled."""
        return self.get("validation", "strict")

    def get_log_level(self) -> str:
        """Get logging level."""
        return self.get("logging", "level")

    def get_log_path_pattern(self) -> str:
        """Get log path pattern."""
        return self.get("logging", "log_path")

    def reload(self) -> None:
        """Reload configuration from file and environment."""
        self._config = self._load_config()

    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dict."""
        return self._deep_copy(self._config)
