"""Unit tests for DockerConfig."""


from src.sandbox.docker_config import DockerConfig


def test_default_config():
    """Test default DockerConfig values."""
    config = DockerConfig()

    assert config.image == "python:3.11-slim"
    assert config.cpu_quota == 100000
    assert config.memory_limit == "512m"
    assert config.network_mode == "none"
    assert config.read_only_root is False
    assert config.timeout_sec == 300
    assert config.extra_env == {}
    assert config.workspace_mount == "/workspace"


def test_custom_config():
    """Test custom DockerConfig values."""
    config = DockerConfig(
        image="python:3.12-slim",
        cpu_quota=200000,
        memory_limit="1g",
        network_mode="bridge",
        read_only_root=True,
        timeout_sec=600,
        extra_env={"MY_VAR": "value"},
        workspace_mount="/app",
    )

    assert config.image == "python:3.12-slim"
    assert config.cpu_quota == 200000
    assert config.memory_limit == "1g"
    assert config.network_mode == "bridge"
    assert config.read_only_root is True
    assert config.timeout_sec == 600
    assert config.extra_env == {"MY_VAR": "value"}
    assert config.workspace_mount == "/app"


def test_to_run_kwargs_contains_required_keys():
    """Test that to_run_kwargs returns all required keys."""
    config = DockerConfig()
    kwargs = config.to_run_kwargs()

    assert "image" in kwargs
    assert "cpu_quota" in kwargs
    assert "mem_limit" in kwargs
    assert "network_mode" in kwargs
    assert "read_only" in kwargs
    assert "environment" in kwargs
    assert "working_dir" in kwargs
    assert "detach" in kwargs
    assert "remove" in kwargs


def test_to_run_kwargs_values():
    """Test that to_run_kwargs maps values correctly."""
    config = DockerConfig(
        image="python:3.11-slim",
        cpu_quota=50000,
        memory_limit="256m",
        network_mode="none",
        read_only_root=True,
        extra_env={"KEY": "val"},
        workspace_mount="/work",
    )
    kwargs = config.to_run_kwargs()

    assert kwargs["image"] == "python:3.11-slim"
    assert kwargs["cpu_quota"] == 50000
    assert kwargs["mem_limit"] == "256m"
    assert kwargs["network_mode"] == "none"
    assert kwargs["read_only"] is True
    assert kwargs["environment"] == {"KEY": "val"}
    assert kwargs["working_dir"] == "/work"
    assert kwargs["detach"] is True
    assert kwargs["remove"] is False  # cleanup handled separately


def test_network_isolation_default():
    """Test that network is isolated by default."""
    config = DockerConfig()
    kwargs = config.to_run_kwargs()

    assert kwargs["network_mode"] == "none"


def test_cpu_quota_one_cpu():
    """Test that default CPU quota equals 1 CPU."""
    config = DockerConfig()
    # 100000 microseconds per 100000 period = 1 CPU
    assert config.cpu_quota == 100000


def test_extra_env_empty_by_default():
    """Test that extra_env is empty dict by default (not shared mutable)."""
    config1 = DockerConfig()
    config2 = DockerConfig()

    config1.extra_env["KEY"] = "value"
    assert "KEY" not in config2.extra_env
