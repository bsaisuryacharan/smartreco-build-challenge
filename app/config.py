from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MESH_API_KEY: str = ""
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    DATABASE_URL: str = "sqlite:///./smartreco.db"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    LANGCHAIN_TRACING_V2: str = "false"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "smartreco"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    DIGEST_FROM_EMAIL: str = "noreply@smartreco.ai"
    DIGEST_HOUR: int = 9

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
