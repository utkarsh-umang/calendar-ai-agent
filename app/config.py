from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    SECRET_KEY: str
    REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    MONGODB_URL: str = "mongodb://mongo:27017"

    class Config:
        env_file = ".env"


settings = Settings()
