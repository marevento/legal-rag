"""Azure AI Search index management for norm documents."""

from __future__ import annotations

import logging

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

logger = logging.getLogger(__name__)


class SearchManager:
    """Manage Azure AI Search index for Mietrecht norms."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        index_name: str,
        embedding_dimensions: int = 3072,
    ) -> None:
        self.endpoint = endpoint
        self.credential = AzureKeyCredential(api_key)
        self.index_name = index_name
        self.embedding_dimensions = embedding_dimensions

        self.index_client = SearchIndexClient(
            endpoint=endpoint,
            credential=self.credential,
        )
        self.search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=self.credential,
        )

    def create_or_update_index(self) -> None:
        """Create or update the search index with hybrid search configuration."""
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SimpleField(name="norm_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="gesetz", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="paragraph", type=SearchFieldDataType.String, filterable=True, sortable=True),
            SearchableField(name="titel", type=SearchFieldDataType.String),
            SearchableField(name="text", type=SearchFieldDataType.String, analyzer_name="de.microsoft"),
            SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="de.microsoft"),
            SimpleField(name="url", type=SearchFieldDataType.String),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.embedding_dimensions,
                vector_search_profile_name="mietrecht-vector-profile",
            ),
        ]

        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(name="mietrecht-hnsw"),
            ],
            profiles=[
                VectorSearchProfile(
                    name="mietrecht-vector-profile",
                    algorithm_configuration_name="mietrecht-hnsw",
                ),
            ],
        )

        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search,
        )

        self.index_client.create_or_update_index(index)
        logger.info("Created/updated index '%s'", self.index_name)

    def upload_documents(self, documents: list[dict]) -> int:
        """Upload documents to the search index.

        Args:
            documents: List of document dicts with all index fields.

        Returns:
            Number of successfully uploaded documents.
        """
        result = self.search_client.upload_documents(documents)
        succeeded = sum(1 for r in result if r.succeeded)
        failed = sum(1 for r in result if not r.succeeded)

        if failed > 0:
            logger.warning("%d documents failed to upload", failed)
        logger.info("Uploaded %d documents to index '%s'", succeeded, self.index_name)
        return succeeded

    def delete_index(self) -> None:
        """Delete the search index."""
        self.index_client.delete_index(self.index_name)
        logger.info("Deleted index '%s'", self.index_name)

    def get_document_count(self) -> int:
        """Get the number of documents in the index."""
        # Use a match-all search with zero results to get count
        results = self.search_client.search(search_text="*", top=0, include_total_count=True)
        return results.get_count() or 0
