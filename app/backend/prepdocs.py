"""Ingestion CLI: Download, parse, embed, and upload Mietrecht norms."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure the backend directory is on the path
sys.path.insert(0, str(Path(__file__).parent))

import config
from prepdocslib.bmj_xml_parser import download_bgb_xml, parse_bgb_xml
from prepdocslib.embeddings import EmbeddingGenerator
from prepdocslib.norm_chunker import chunk_norms
from prepdocslib.search_manager import SearchManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Mietrecht norms into Azure AI Search")
    parser.add_argument("--download", action="store_true", help="Download BGB XML from BMJ")
    parser.add_argument("--skip-upload", action="store_true", help="Parse and cache only, skip Azure upload")
    parser.add_argument("--recreate-index", action="store_true", help="Delete and recreate the search index")
    parser.add_argument("--semantic-ranker", action="store_true", help="Enable semantic ranker (requires Standard tier)")
    parser.add_argument("--xml-path", type=str, default=None, help="Path to BGB XML file (skip download)")
    args = parser.parse_args()

    data_dir = Path(config.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    xml_path = Path(args.xml_path) if args.xml_path else data_dir / "bgb_mietrecht.xml"

    # Step 1: Download XML
    if args.download or not xml_path.exists():
        logger.info("Step 1: Downloading BGB XML...")
        download_bgb_xml(config.BMJ_XML_URL, xml_path)
    else:
        logger.info("Step 1: Using existing XML at %s", xml_path)

    # Step 2: Parse and filter Mietrecht norms
    logger.info("Step 2: Parsing Mietrecht norms...")
    norms = parse_bgb_xml(xml_path, config.MIETRECHT_RANGE_START, config.MIETRECHT_RANGE_END)
    if not norms:
        logger.error("No norms extracted. Check XML format.")
        sys.exit(1)
    logger.info("Extracted %d norms", len(norms))

    # Step 3: Generate norm_cache.json
    logger.info("Step 3: Generating norm_cache.json...")
    cache_path = Path(config.NORM_CACHE_PATH)
    cache_data = {norm.norm_id: norm.model_dump() for norm in norms}
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    logger.info("Wrote norm cache to %s (%d entries)", cache_path, len(cache_data))

    if args.skip_upload:
        logger.info("Skipping Azure upload (--skip-upload)")
        return

    # Step 4: Create search index
    logger.info("Step 4: Setting up Azure AI Search index...")
    search_mgr = SearchManager(
        endpoint=config.AZURE_SEARCH_ENDPOINT,
        api_key=config.AZURE_SEARCH_API_KEY,
        index_name=config.AZURE_SEARCH_INDEX,
        semantic_config_name=config.AZURE_SEARCH_SEMANTIC_CONFIG,
        embedding_dimensions=config.AZURE_OPENAI_EMBEDDING_DIMENSIONS,
    )

    if args.recreate_index:
        logger.info("Recreating index...")
        try:
            search_mgr.delete_index()
        except Exception as exc:
            # ResourceNotFoundError is expected if index doesn't exist yet
            if "ResourceNotFoundError" not in type(exc).__name__:
                logger.warning("Unexpected error deleting index: %s", exc)

    search_mgr.create_or_update_index(use_semantic_ranker=args.semantic_ranker)

    # Step 5: Chunk norms into documents
    logger.info("Step 5: Chunking norms...")
    documents = chunk_norms(norms)

    # Step 6: Generate embeddings
    logger.info("Step 6: Generating embeddings...")
    embedder = EmbeddingGenerator(
        endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_API_KEY,
        deployment=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        api_version=config.AZURE_OPENAI_API_VERSION,
        dimensions=config.AZURE_OPENAI_EMBEDDING_DIMENSIONS,
    )

    content_texts = [doc["content"] for doc in documents]
    embeddings = embedder.generate(content_texts)

    for doc, embedding in zip(documents, embeddings):
        doc["content_vector"] = embedding

    # Step 7: Upload to Azure AI Search
    logger.info("Step 7: Uploading documents...")
    uploaded = search_mgr.upload_documents(documents)
    logger.info("Done! %d documents uploaded to index '%s'", uploaded, config.AZURE_SEARCH_INDEX)


if __name__ == "__main__":
    main()
