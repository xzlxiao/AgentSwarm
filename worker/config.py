from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    gateway_url: str = ""
    agent_node_id: str = ""
    agent_internal_key: str = "default-internal-key"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }
