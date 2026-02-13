"""Configuration constants for the legal-rag backend."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_CHAT_MINI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_MINI_DEPLOYMENT", "gpt-4o-mini")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
AZURE_OPENAI_EMBEDDING_DIMENSIONS = int(os.environ.get("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "3072"))

# Azure AI Search
AZURE_SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX", "mietrecht-norms")

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_CONTAINER = os.environ.get("AZURE_STORAGE_CONTAINER", "documents")

# Authentication (magic-link)
JWT_SECRET = os.environ.get("JWT_SECRET", "")
ADMIN_EMAILS = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]
APP_URL = os.environ.get("APP_URL", "http://localhost:50505")
AZURE_COMMUNICATION_CONNECTION_STRING = os.environ.get("AZURE_COMMUNICATION_CONNECTION_STRING", "")
ACS_SENDER_ADDRESS = os.environ.get("ACS_SENDER_ADDRESS", "")

# CORS
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "")  # e.g. "https://my-frontend.azurecontainerapps.io"

# RAG Configuration
RAG_APPROACH = os.environ.get("RAG_APPROACH", "custom")  # "custom" or "langchain"
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "5"))
RAG_TEMPERATURE = float(os.environ.get("RAG_TEMPERATURE", "0"))
RAG_SEARCH_STRATEGY = os.environ.get("RAG_SEARCH_STRATEGY", "hybrid")  # "bm25", "vector", "hybrid"

# Paths
# In container: /app/data. Locally: ../../data relative to this file.
_default_data = os.path.join(os.path.dirname(__file__), "..", "..", "data")
if not os.path.exists(_default_data):
    _default_data = os.path.join(os.path.dirname(__file__), "data")
DATA_DIR = os.environ.get("DATA_DIR", _default_data)
PERSIST_DIR = os.environ.get("PERSIST_DIR", DATA_DIR)
NORM_CACHE_PATH = os.path.join(DATA_DIR, "norm_cache.json")

# BMJ XML
BMJ_XML_URL = "https://www.gesetze-im-internet.de/bgb/xml.zip"
MIETRECHT_RANGE_START = 535
MIETRECHT_RANGE_END = 580  # inclusive of 580a


def validate_config() -> list[str]:
    """Check that required config values are set. Returns list of missing var names."""
    required = {
        "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
        "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
        "AZURE_SEARCH_ENDPOINT": AZURE_SEARCH_ENDPOINT,
        "AZURE_SEARCH_API_KEY": AZURE_SEARCH_API_KEY,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        logger.warning("Missing required config: %s", ", ".join(missing))
    return missing
