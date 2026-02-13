"""Quart application factory and routes."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI
from quart import Quart, g, jsonify, request, send_from_directory
from quart.typing import ResponseReturnValue
from quart_cors import cors

import config
from approaches.approach import Approach
from approaches.chat_rag import ChatRAGApproach
from core.auth_routes import auth_bp
from core.authentication import require_auth, require_role
from core.usage_tracker import get_daily_chat_count, get_usage_stats, init_db, log_request
from models.chat import ChatRequest
from postprocessing.citation_injection import norm_cache

logger = logging.getLogger(__name__)


STATIC_DIR = Path(__file__).parent / "static"
EVAL_RESULTS_PATH = Path(config.PERSIST_DIR) / "eval_results.json"
DAILY_QUERY_LIMIT = int(os.environ.get("DAILY_QUERY_LIMIT", "100"))


def create_app() -> Quart:
    app = Quart(__name__, static_folder=str(STATIC_DIR) if STATIC_DIR.exists() else None)
    app.config["MAX_CONTENT_LENGTH"] = 1_000_000  # 1MB request body limit

    # CORS — restrict to configured origin; allow all only in dev (no JWT_SECRET)
    allowed_origin = config.CORS_ORIGIN or (
        "*" if not config.JWT_SECRET else f"{config.APP_URL}"
    )
    app = cors(app, allow_origin=allowed_origin)

    @app.after_request
    async def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if config.JWT_SECRET:  # production
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

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

    # Initialize usage tracking
    init_db()

    # Register auth blueprint
    app.register_blueprint(auth_bp)

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
        if DAILY_QUERY_LIMIT and get_daily_chat_count() >= DAILY_QUERY_LIMIT:
            return jsonify({"error": "Daily query limit reached. Please try again tomorrow."}), 429

        from pydantic import ValidationError

        data = await request.get_json()
        try:
            chat_request = ChatRequest.model_validate(data)
        except ValidationError as e:
            return jsonify({"error": e.errors()}), 422

        approach_name = chat_request.approach or config.RAG_APPROACH
        approach = _get_approach(app, approach_name)

        start = time.perf_counter()
        response = await approach.run(chat_request)
        latency_ms = (time.perf_counter() - start) * 1000

        log_request(
            user_email=getattr(g, "user_email", "unknown"),
            endpoint="/chat",
            method="POST",
            query=chat_request.messages[-1].content if chat_request.messages else None,
            search_strategy=chat_request.search_strategy,
            confidence=response.confidence,
            citation_count=len(response.sources),
            latency_ms=latency_ms,
            metadata={"approach": approach_name},
        )

        return jsonify(response.model_dump())

    @app.route("/chat/stream", methods=["POST"])
    @require_auth
    async def chat_stream() -> ResponseReturnValue:
        if DAILY_QUERY_LIMIT and get_daily_chat_count() >= DAILY_QUERY_LIMIT:
            return jsonify({"error": "Daily query limit reached. Please try again tomorrow."}), 429

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

    # --- Evaluation ---

    _eval_state: dict = {"running": False, "progress": None, "report": None, "last_run_at": 0.0}
    EVAL_TIMEOUT = 600  # 10 minutes max

    # Load cached eval results on startup
    if EVAL_RESULTS_PATH.exists():
        try:
            _eval_state["report"] = json.loads(EVAL_RESULTS_PATH.read_text(encoding="utf-8"))
            logger.info("Loaded cached evaluation results from %s", EVAL_RESULTS_PATH)
        except Exception:
            logger.warning("Failed to load cached evaluation results", exc_info=True)

    @app.route("/evaluate", methods=["POST"])
    @require_auth
    @require_role("admin")
    async def evaluate() -> ResponseReturnValue:
        """Start evaluation in the background (admin only)."""
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
        query_transforms = data.get("query_transforms", ["none"])
        decompose_options = data.get("decompose_options", [False])
        top_k = data.get("top_k", 5)

        golden_path = Path(config.DATA_DIR) / "golden_dataset.jsonl"
        if not golden_path.exists():
            return jsonify({"error": "Golden dataset not found"}), 404

        examples = load_golden_dataset(golden_path)[:MAX_EXAMPLES]
        approach = _get_approach(app, data.get("approach", config.RAG_APPROACH))

        _eval_state["last_run_at"] = time.time()

        async def run_in_background():
            _eval_state["running"] = True
            _eval_state["progress"] = None
            _eval_state["report"] = None
            start = time.time()
            try:
                async for event in run_evaluation_stream(
                    approach=approach,
                    openai_client=app.config["openai_client"],
                    examples=examples,
                    strategies=strategies,
                    query_transforms=query_transforms,
                    decompose_options=decompose_options,
                    top_k=top_k,
                ):
                    # Timeout check
                    if time.time() - start > EVAL_TIMEOUT:
                        logger.warning("Evaluation timed out after %ds", EVAL_TIMEOUT)
                        break

                    if isinstance(event, EvalProgress):
                        _eval_state["progress"] = {
                            "completed": event.completed,
                            "total": event.total,
                            "config_label": event.config_label,
                            "question": event.question,
                            "status": event.status,
                        }
                    elif isinstance(event, MetricsReport):
                        report_data = event.model_dump()
                        _eval_state["report"] = report_data
                        # Persist to disk for viewers
                        try:
                            EVAL_RESULTS_PATH.write_text(
                                json.dumps(report_data, ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                            logger.info("Evaluation results saved to %s", EVAL_RESULTS_PATH)
                        except Exception:
                            logger.exception("Failed to persist evaluation results")
            finally:
                _eval_state["running"] = False

            log_request(
                user_email=getattr(g, "user_email", "admin"),
                endpoint="/evaluate",
                method="POST",
                latency_ms=(time.time() - start) * 1000,
                metadata={"strategies": strategies, "query_transforms": query_transforms, "examples": len(examples)},
            )

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

    # --- Admin ---

    @app.route("/admin/usage", methods=["GET"])
    @require_auth
    @require_role("admin")
    async def admin_usage() -> ResponseReturnValue:
        """Return usage analytics (admin only)."""
        return jsonify(get_usage_stats())

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
