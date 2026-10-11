
from sqlalchemy import create_engine, text
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True
)

with engine.connect() as connection:
    result = connection.execute(
        text("SELECT current_database(), current_user")
    )

    print("Database connection successful!")
    print("Database and user:", result.fetchone())
