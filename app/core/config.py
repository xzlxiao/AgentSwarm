from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://mongodb:27017"
    mongo_db_name: str = "agentswarm"
    hermes_api_base: str = ""
    hermes_api_key: str = ""
    hermes_model: str = "hunyuan-2.0-instruct-20251111"
    swarm_network_name: str = "agentswarm-net"
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    agent_internal_key: str = "default-internal-key"
    snapshot_base_dir: str = "./snapshots"
    log_level: str = "info"
    lock_reclaim_interval_seconds: int = 30
    default_lock_timeout_seconds: int = 600

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
