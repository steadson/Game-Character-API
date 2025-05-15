import os
import secrets
from typing import List, Union, Optional

from pydantic import AnyHttpUrl, PostgresDsn, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    APP_NAME: str = "Game Character API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    PUBLIC_API_KEY: str = os.getenv("PUBLIC_API_KEY", "42f27353fg4624f846ge64wdfg4y49iw")
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    SUPER_ADMIN_SECRET_TOKEN: str =os.getenv("SUPER_ADMIN_SECRET_TOKEN", "12345678")  # CHANGE THIS!

    SERVER_HOST: AnyHttpUrl = "http://localhost:8000"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    DATABASE_URL: str = "sqlite:///./app.db"

    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # Document Storage
    DOCUMENT_STORAGE_PATH: str = "./storage/documents"
    VECTOR_DB_PATH: str = "./storage/vectordb"
    
    # Admin Configuration
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "change-this-password"
    ADMIN_EMAIL: str = "admin@example.com"
    
    # JWT Token Config
    ALGORITHM: str = "HS256"
    
    # Debug Mode
    DEBUG: bool = False

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()