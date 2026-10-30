"""
Application configuration for the ResearchDesk AI Research Agent.
Loads settings from environment variables with sensible defaults.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    app_name: str = "ResearchDesk API"
    app_version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = "/api"

    # LLM Settings
    # Supports "openai", "groq", "gemini", "openrouter", "local"
    llm_provider: str = Field(default="openai", description="LLM provider name")
    llm_api_key: Optional[str] = Field(default=None, description="Primary LLM API key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    groq_api_key: Optional[str] = Field(default=None, description="Groq API key")
    gemini_api_key: Optional[str] = Field(default=None, description="Gemini API key")

    llm_model: str = Field(default="gpt-4o-mini", description="LLM model identifier")
    llm_base_url: Optional[str] = Field(
        default=None, description="Custom base URL for OpenAI-compatible endpoint"
    )
    llm_temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    llm_max_tokens: int = Field(default=3500, ge=500, le=8000)
    llm_timeout_seconds: int = Field(default=45, ge=5, le=120)

    # Tool & Retrieval Settings
    # Search provider: "duckduckgo", "tavily", "serper"
    search_provider: str = Field(
        default="duckduckgo", description="Search engine provider"
    )
    tavily_api_key: Optional[str] = Field(default=None, description="Tavily API key")
    serper_api_key: Optional[str] = Field(default=None, description="Serper API key")

    max_search_results: int = Field(default=5, ge=1, le=10)
    max_scraped_pages: int = Field(default=3, ge=0, le=6)
    http_timeout_seconds: int = Field(default=15, ge=3, le=60)
    max_tool_retries: int = Field(default=2, ge=0, le=5)
    page_char_limit: int = Field(default=6000, ge=500, le=20000)

    # Prompt safety
    strip_prompt_injection_tokens: bool = True

    @property
    def effective_api_key(self) -> Optional[str]:
        """Resolves the active API key based on provider preference."""
        if self.llm_api_key:
            return self.llm_api_key
        if self.llm_provider.lower() == "groq" and self.groq_api_key:
            return self.groq_api_key
        if self.llm_provider.lower() == "gemini" and self.gemini_api_key:
            return self.gemini_api_key
        if self.openai_api_key:
            return self.openai_api_key
        return None

    @property
    def is_llm_configured(self) -> bool:
        """Returns True if a usable LLM API key is present."""
        key = self.effective_api_key
        return bool(key and not key.startswith("your_") and len(key.strip()) > 5)


settings = Settings()
