"""Shared test fixtures."""

import sys
from pathlib import Path

import pytest

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app" / "backend"))

from models.norm import Norm, NormReference


@pytest.fixture
def sample_norms() -> list[Norm]:
    return [
        Norm(
            norm_id="bgb-535",
            gesetz="BGB",
            paragraph="535",
            titel="Inhalt und Hauptpflichten des Mietvertrags",
            text=(
                "(1) Durch den Mietvertrag wird der Vermieter verpflichtet, dem Mieter den Gebrauch "
                "der Mietsache während der Mietzeit zu gewähren. Der Vermieter hat die Mietsache dem "
                "Mieter in einem zum vertragsgemäßen Gebrauch geeigneten Zustand zu überlassen und sie "
                "während der Mietzeit in diesem Zustand zu erhalten."
            ),
            url="https://www.gesetze-im-internet.de/bgb/__535.html",
        ),
        Norm(
            norm_id="bgb-556",
            gesetz="BGB",
            paragraph="556",
            titel="Vereinbarungen über Betriebskosten",
            text=(
                "(1) Die Vertragsparteien können vereinbaren, dass der Mieter Betriebskosten trägt. "
                "Betriebskosten sind die Kosten, die dem Eigentümer oder Erbbauberechtigten durch das "
                "Eigentum oder das Erbbaurecht am Grundstück oder durch den bestimmungsmäßigen Gebrauch "
                "des Gebäudes, der Nebengebäude, Anlagen, Einrichtungen und des Grundstücks laufend entstehen."
            ),
            url="https://www.gesetze-im-internet.de/bgb/__556.html",
        ),
        Norm(
            norm_id="bgb-573",
            gesetz="BGB",
            paragraph="573",
            titel="Ordentliche Kündigung des Vermieters",
            text=(
                "(1) Der Vermieter kann nur kündigen, wenn er ein berechtigtes Interesse an der Beendigung "
                "des Mietverhältnisses hat. (2) Ein berechtigtes Interesse des Vermieters an der Beendigung "
                "des Mietverhältnisses liegt insbesondere vor, wenn der Mieter seine vertraglichen Pflichten "
                "schuldhaft nicht unerheblich verletzt hat."
            ),
            url="https://www.gesetze-im-internet.de/bgb/__573.html",
        ),
    ]


@pytest.fixture
def sample_norm_references(sample_norms: list[Norm]) -> list[NormReference]:
    return [
        NormReference(
            norm_id=n.norm_id,
            paragraph=n.paragraph,
            titel=n.titel,
            text=n.text,
            url=n.url,
            relevance_score=0.95 - i * 0.1,
        )
        for i, n in enumerate(sample_norms)
    ]
