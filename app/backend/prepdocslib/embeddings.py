"""Azure OpenAI embedding generation for norm documents."""

from __future__ import annotations

import logging

from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings using Azure OpenAI."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-10-21",
        dimensions: int = 3072,
    ) -> None:
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self.deployment = deployment
        self.dimensions = dimensions

    def generate(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.
            batch_size: Number of texts per API call.

        Returns:
            List of embedding vectors.
        """
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            logger.info("Embedding batch %d-%d of %d", i, i + len(batch), len(texts))

            response = self.client.embeddings.create(
                model=self.deployment,
                input=batch,
                dimensions=self.dimensions,
            )

            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings
