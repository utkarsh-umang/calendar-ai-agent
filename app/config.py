from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    SECRET_KEY: str
    REDIRECT_URI: str = "http://localhost:9000/auth/callback"
    MONGODB_URL: str = "mongodb://mongo:27017"
    OPENAI_API_KEY: str
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_BASE_URL: str

    class Config:
        env_file = ".env"


settings = Settings()