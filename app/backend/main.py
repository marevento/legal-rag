"""Entry point for the legal-rag backend."""

import logging
import os
import sys
from pathlib import Path

# Ensure the backend directory is on the path
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    app.run(host="127.0.0.1", port=50505, debug=debug)
