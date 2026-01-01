import os

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, environment variables
    # must already be set by the shell or process manager
    pass


class Settings:
    """
    Minimal application settings.
    """
    def __init__(self):
        self.WHG_API_TOKEN = os.getenv("WHG_API_TOKEN")


settings = Settings()
