"""Quart application factory and routes."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI
from quart import Quart, jsonify, request, send_from_directory
from quart.typing import ResponseReturnValue
from quart_cors import cors

import config
from approaches.approach import Approach
from approaches.chat_rag import ChatRAGApproach
from core.authentication import require_auth
from models.chat import ChatRequest
from postprocessing.citation_injection import norm_cache

logger = logging.getLogger(__name__)


STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> Quart:
    app = Quart(__name__, static_folder=str(STATIC_DIR) if STATIC_DIR.exists() else None)
    app.config["MAX_CONTENT_LENGTH"] = 1_000_000  # 1MB request body limit

    # CORS — restrict to configured origin, or allow all in dev
    allowed_origin = config.CORS_ORIGIN or "*"
    app = cors(app, allow_origin=allowed_origin)

    # Initialize clients
    openai_client = AsyncAzureOpenAI(
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_API_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION,
    )

    search_client = SearchClient(
        endpoint=config.AZURE_SEARCH_ENDPOINT,
        index_name=config.AZURE_SEARCH_INDEX,
        credential=AzureKeyCredential(config.AZURE_SEARCH_API_KEY),
    )

    # Initialize approaches
    chat_rag = ChatRAGApproach(
        openai_client=openai_client,
        search_client=search_client,
    )

    # Lazy-import LangChain approach to avoid loading when not needed
    from approaches.chat_langchain import ChatLangChainApproach

    chat_langchain = ChatLangChainApproach(
        openai_client=openai_client,
        search_client=search_client,
    )

    # Store in app config for access in routes
    app.config["chat_rag"] = chat_rag
    app.config["chat_langchain"] = chat_langchain
    app.config["openai_client"] = openai_client
    app.config["search_client"] = search_client

    # Load norm cache
    cache_path = Path(config.NORM_CACHE_PATH)
    if cache_path.exists():
        norm_cache.load(cache_path)
        logger.info("Norm cache loaded (%d norms)", len(norm_cache.norms))
    else:
        logger.warning("Norm cache not found at %s. Run prepdocs.py first.", cache_path)

    # Register routes
    _register_routes(app)

    return app


def _get_approach(app: Quart, approach_name: str) -> Approach:
    """Get the configured RAG approach."""
    if approach_name == "langchain":
        return app.config["chat_langchain"]
    return app.config["chat_rag"]


def _register_routes(app: Quart) -> None:

    @app.route("/health")
    async def health() -> ResponseReturnValue:
        return jsonify({"status": "ok"})

    @app.route("/chat", methods=["POST"])
    @require_auth
    async def chat() -> ResponseReturnValue:
        from pydantic import ValidationError

        data = await request.get_json()
        try:
            chat_request = ChatRequest.model_validate(data)
        except ValidationError as e:
            return jsonify({"error": e.errors()}), 422

        approach_name = chat_request.approach or config.RAG_APPROACH
        approach = _get_approach(app, approach_name)

        response = await approach.run(chat_request)
        return jsonify(response.model_dump())

    @app.route("/chat/stream", methods=["POST"])
    @require_auth
    async def chat_stream() -> ResponseReturnValue:
        from pydantic import ValidationError

        data = await request.get_json()
        try:
            chat_request = ChatRequest.model_validate(data)
        except ValidationError as e:
            return jsonify({"error": e.errors()}), 422

        approach_name = chat_request.approach or config.RAG_APPROACH
        approach = _get_approach(app, approach_name)

        async def generate():
            async for delta in approach.run_stream(chat_request):
                yield f"data: {json.dumps(delta.model_dump())}\n\n"

        return generate(), 200, {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Transfer-Encoding": "chunked",
        }

    @app.route("/config", methods=["GET"])
    @require_auth
    async def get_config() -> ResponseReturnValue:
        """Return client-side configuration."""
        return jsonify({
            "search_strategy": config.RAG_SEARCH_STRATEGY,
            "temperature": config.RAG_TEMPERATURE,
            "top_k": config.RAG_TOP_K,
            "use_semantic_ranker": config.AZURE_SEARCH_USE_SEMANTIC_RANKER,
            "approach": config.RAG_APPROACH,
        })

    @app.route("/norms", methods=["GET"])
    @require_auth
    async def list_norms() -> ResponseReturnValue:
        """List all norms in the cache."""
        norms = [
            {"norm_id": n.norm_id, "paragraph": n.paragraph, "titel": n.titel, "url": n.url}
            for n in norm_cache.norms.values()
        ]
        return jsonify(norms)

    # In-memory evaluation state for polling
    _eval_state: dict = {"running": False, "progress": None, "report": None}

    @app.route("/evaluate", methods=["POST"])
    @require_auth
    async def evaluate() -> ResponseReturnValue:
        """Start evaluation in the background."""
        import asyncio

        from evaluation.evaluator import (
            EvalProgress,
            load_golden_dataset,
            run_evaluation_stream,
        )
        from models.evaluation import MetricsReport

        if _eval_state["running"]:
            return jsonify({"error": "Evaluation already running"}), 409

        MAX_EXAMPLES = 50

        data = await request.get_json() or {}
        strategies = data.get("strategies", ["bm25", "vector", "hybrid"])
        top_k = data.get("top_k", 5)

        golden_path = Path(config.DATA_DIR) / "golden_dataset.jsonl"
        if not golden_path.exists():
            return jsonify({"error": "Golden dataset not found"}), 404

        examples = load_golden_dataset(golden_path)[:MAX_EXAMPLES]
        approach = _get_approach(app, data.get("approach", config.RAG_APPROACH))

        async def run_in_background():
            _eval_state["running"] = True
            _eval_state["progress"] = None
            _eval_state["report"] = None
            try:
                async for event in run_evaluation_stream(
                    approach=approach,
                    openai_client=app.config["openai_client"],
                    examples=examples,
                    strategies=strategies,
                    top_k=top_k,
                ):
                    if isinstance(event, EvalProgress):
                        _eval_state["progress"] = {
                            "completed": event.completed,
                            "total": event.total,
                            "strategy": event.strategy,
                            "question": event.question,
                            "status": event.status,
                        }
                    elif isinstance(event, MetricsReport):
                        _eval_state["report"] = event.model_dump()
            finally:
                _eval_state["running"] = False

        asyncio.ensure_future(run_in_background())
        return jsonify({"status": "started"})

    @app.route("/evaluate/status", methods=["GET"])
    @require_auth
    async def evaluate_status() -> ResponseReturnValue:
        """Poll evaluation progress."""
        return jsonify({
            "running": _eval_state["running"],
            "progress": _eval_state["progress"],
            "report": _eval_state["report"],
        })

    # Serve frontend SPA (when static files are bundled)
    if STATIC_DIR.exists():

        @app.route("/")
        async def index() -> ResponseReturnValue:
            return await send_from_directory(str(STATIC_DIR), "index.html")

        @app.route("/<path:path>")
        async def static_files(path: str) -> ResponseReturnValue:
            file_path = STATIC_DIR / path
            if file_path.is_file():
                return await send_from_directory(str(STATIC_DIR), path)
            # SPA fallback — serve index.html for client-side routes
            return await send_from_directory(str(STATIC_DIR), "index.html")

    @app.errorhandler(400)
    async def bad_request(e: Exception) -> ResponseReturnValue:
        return jsonify({"error": str(e)}), 400

    @app.errorhandler(413)
    async def payload_too_large(e: Exception) -> ResponseReturnValue:
        return jsonify({"error": "Request payload too large"}), 413

    @app.errorhandler(422)
    async def validation_error(e: Exception) -> ResponseReturnValue:
        return jsonify({"error": str(e)}), 422

    @app.errorhandler(401)
    async def unauthorized(e: Exception) -> ResponseReturnValue:
        return jsonify({"error": "Authentication required"}), 401

    @app.errorhandler(500)
    async def server_error(e: Exception) -> ResponseReturnValue:
        logger.exception("Internal server error")
        return jsonify({"error": "Internal server error"}), 500
