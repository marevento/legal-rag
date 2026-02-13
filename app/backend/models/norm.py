"""Norm data models for German legal texts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Norm(BaseModel):
    """A single legal norm (paragraph) from BGB Mietrecht."""

    norm_id: str = Field(description="Unique identifier, e.g. 'bgb-535'")
    gesetz: str = Field(default="BGB", description="Law abbreviation")
    paragraph: str = Field(description="Paragraph number, e.g. '535'")
    titel: str = Field(default="", description="Title of the paragraph")
    text: str = Field(description="Full norm text")
    url: str = Field(default="", description="URL to gesetze-im-internet.de")

    @property
    def display_name(self) -> str:
        return f"§{self.paragraph} {self.gesetz}"


class NormReference(BaseModel):
    """A reference to a norm used in a RAG response."""

    norm_id: str
    paragraph: str
    titel: str
    text: str
    url: str
    relevance_score: float = Field(default=0.0, description="Search relevance score")
