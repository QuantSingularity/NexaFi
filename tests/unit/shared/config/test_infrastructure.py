from typing import Any
import os
from unittest.mock import patch


class InfrastructureConfig:
    """Simulates the class being tested."""

    def __init__(self) -> None:
        self.redis_host = os.environ.get("REDIS_HOST", "default_host")
        self.redis_port = int(os.environ.get("REDIS_PORT", "6379"))


class TestInfrastructureConfig:

    @patch.dict(os.environ, {"REDIS_HOST": "test_redis_host", "REDIS_PORT": "6380"})
    def test_infrastructure_config_loads_from_env(self) -> Any:
        """
        Test that InfrastructureConfig correctly loads values
        from environment variables when they are set.
        """
        config = InfrastructureConfig()
        assert config.redis_host == "test_redis_host"
        assert config.redis_port == 6380
        assert os.environ["REDIS_HOST"] == "test_redis_host"
        assert os.environ["REDIS_PORT"] == "6380"
