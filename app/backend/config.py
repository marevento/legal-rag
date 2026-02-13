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
AZURE_SEARCH_SEMANTIC_CONFIG = os.environ.get("AZURE_SEARCH_SEMANTIC_CONFIG", "mietrecht-semantic")
AZURE_SEARCH_USE_SEMANTIC_RANKER = os.environ.get("AZURE_SEARCH_USE_SEMANTIC_RANKER", "false").lower() == "true"

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_CONTAINER = os.environ.get("AZURE_STORAGE_CONTAINER", "documents")

# Authentication
AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")

# CORS
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "")  # e.g. "https://my-frontend.azurecontainerapps.io"

# RAG Configuration
RAG_APPROACH = os.environ.get("RAG_APPROACH", "custom")  # "custom" or "langchain"
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "5"))
RAG_TEMPERATURE = float(os.environ.get("RAG_TEMPERATURE", "0"))
RAG_SEARCH_STRATEGY = os.environ.get("RAG_SEARCH_STRATEGY", "hybrid")  # "bm25", "vector", "hybrid"

# Paths
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data"))
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
