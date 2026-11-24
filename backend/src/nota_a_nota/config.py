from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/nota_a_nota"
    auth_jwks_url: str | None = "http://localhost:3100/api/auth/jwks"
    auth_issuer: str = "http://localhost:3100"
    auth_audience: str = "nota-a-nota-api"
    anthropic_api_key: str | None = None
    voyage_api_key: str | None = None

    modelo_categorizacao: str = "claude-haiku-5-5"
    modelo_analise: str = "claude-haiku-5-5"
    modelo_embedding: str = "voyage-4-lite"
    esforco_chat: str = "low"
    db_pool_size: int = 2
    db_max_overflow: int = 3
    analise_pensar: bool = True
    analise_esforco: str = "medium"
    pesquisa_web: str = ""
    pesquisa_web_max_por_analise: int = 6

    @field_validator("database_url")
    @classmethod
    def usar_driver_psycopg(cls, valor: str) -> str:
        for prefixo in ("postgres://", "postgresql://"):
            if valor.startswith(prefixo):
                return "postgresql+psycopg://" + valor.removeprefix(prefixo)
        return valor


@lru_cache
def get_settings() -> Settings:
    return Settings()
