from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/tracer"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    result_row_limit: int = 10000

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
