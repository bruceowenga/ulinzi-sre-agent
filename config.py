from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    prometheus_url: str = "http://localhost:9090"
    loki_url: str = "http://localhost:3100"
    grafana_url: str = "http://localhost:3000"
    grafana_api_key: str = ""
    ntfy_url: str = "http://localhost:8070"
    ntfy_token: str = ""
    ntfy_topic: str = "odin-alerts"
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    primary_model: str = 'qwen2.5:1.5b'
    fallback_model: str = 'phi3.5:mini'
    confidence_threshold: float = 0.6
    dry_run: bool = False


settings = Settings()