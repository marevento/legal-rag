"""Entry point for the legal-rag backend."""

import logging
import os
import sys
from pathlib import Path

# Ensure the backend directory is on the path
sys.path.insert(0, str(Path(__file__).parent))

# Configure Azure Monitor if connection string is available (deployed on Azure).
# Must be called before any other logging/instrumentation setup.
_appinsights_conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
if _appinsights_conn:
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=_appinsights_conn)

from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = create_app()

if __name__ == "__main__":
    from hypercorn.config import Config as HypercornConfig

    debug = os.environ.get("DEBUG", "false").lower() == "true"
    hconfig = HypercornConfig()
    host = os.environ.get("HOST", "127.0.0.1")
    hconfig.bind = [f"{host}:50505"]
    hconfig.response_timeout = 600  # 10 minutes (for evaluation SSE streams)

    import asyncio
    from hypercorn.asyncio import serve

    asyncio.run(serve(app, hconfig))
