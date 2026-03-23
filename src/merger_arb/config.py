"""Centralised settings — loaded once at startup."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    tavily_api_key: str
    edgar_user_agent: str = "MergerArbResearch research@example.com"

    # Model routing
    analysis_model: str = "claude-opus-4-6"       # deep synthesis
    fast_model: str = "claude-sonnet-4-6"          # tool calls / intermediate steps

    # EDGAR throttle — be a good citizen, free service
    edgar_requests_per_second: float = 5.0


settings = Settings()  # type: ignore[call-arg]
