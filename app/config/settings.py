"""Configuration centralisée pour Call Shadow AI Agent."""

from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """Configuration de l'application chargée depuis .env"""
    
    # OpenAI
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.7, alias="OPENAI_TEMPERATURE")
    openai_max_tokens: int = Field(default=500, alias="OPENAI_MAX_TOKENS")
    
    # Application
    app_name: str = Field(default="Call Shadow AI Agent", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # API
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    cors_origins: str = Field(default='["*"]', alias="CORS_ORIGINS")
    
    # Weaviate (optionnel pour plus tard)
    weaviate_url: str | None = Field(default=None, alias="WEAVIATE_URL")
    weaviate_api_key: str | None = Field(default=None, alias="WEAVIATE_API_KEY")
    weaviate_class: str = Field(default="ConversationKnowledge", alias="WEAVIATE_CLASS")
    
    # Memory
    max_memory_messages: int = Field(default=50, alias="MAX_MEMORY_MESSAGES")
    memory_summary_enabled: bool = Field(default=False, alias="MEMORY_SUMMARY_ENABLED")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def get_cors_origins(self) -> List[str]:
        """Parse CORS origins depuis la config."""
        import json
        try:
            return json.loads(self.cors_origins)
        except:
            return ["*"]


# Instance globale des settings
settings = Settings()

