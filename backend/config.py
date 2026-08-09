from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.
    Uses pydantic-settings for validation and type coercion.
    """

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # LLM Providers
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    # Default provider settings
    DEFAULT_LLM_PROVIDER: str = "gemini"
    DEFAULT_LLM_MODEL: str = "gemini-2.0-flash"

    # Embeddings
    VOYAGE_API_KEY: str = ""
    DEFAULT_EMBED_MODEL: str = "voyage-02"

    # Widget Security
    WIDGET_JWT_SECRET: str = "change-this-in-production"
    WIDGET_TOKEN_EXPIRE_MINUTES: int = 60

    # Rate limiting
    MAX_REQUESTS_PER_HOUR_PER_IP: int = 100
    MAX_REQUESTS_PER_DAY_PER_BOT: int = 1000

    # Environment
    ENVIRONMENT: str = "development"

    # Vector Database
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "sitesense-ai"

    # ChromaDB (Legacy)
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_PERSIST_PATH: str = "./data/chroma"

    # SQLite
    SQLITE_DB_PATH: str = "./data/sitesense.db"

    # Server URLs
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # File uploads
    UPLOADS_DIR: str = "./uploads"

    model_config = {
        "env_file": "../.env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
