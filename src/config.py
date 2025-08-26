"""
Application configuration using Pydantic settings
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Environment
    environment: str = "production"
    log_level: str = "INFO"
    debug: bool = False
    
    # API Configuration
    api_v1_str: str = "/api/v1"
    secret_key: str = "super_secret_key_change_in_production"
    
    # Database
    postgres_host: str = "postgresql"
    postgres_port: int = 5432
    postgres_user: str = "dj_agent"
    postgres_password: str = "password"
    postgres_db: str = "dj_agent"
    
    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # External APIs
    openai_api_key: Optional[str] = None
    pinecone_api_key: Optional[str] = None
    pinecone_environment: Optional[str] = None
    
    # Monitoring
    metrics_enabled: bool = True
    metrics_port: int = 9090
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()