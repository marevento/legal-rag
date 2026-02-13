"""Parse BMJ XML format for German federal laws.

Downloads and parses the official XML from gesetze-im-internet.de,
filtering to Mietrecht paragraphs (§§535-580a BGB).
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path

import httpx
from lxml import etree

from models.norm import Norm
from postprocessing.url_generator import generate_norm_url

logger = logging.getLogger(__name__)

# BMJ XML namespaces
NAMESPACES = {
    "akn": "http://Inhaltsdaten.LegalDocML.de/1.7.2/",
}


def download_bgb_xml(url: str, output_path: Path) -> Path:
    """Download BGB XML zip and extract to output_path."""
    logger.info("Downloading BGB XML from %s", url)
    response = httpx.get(url, follow_redirects=True, timeout=60)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        xml_files = [f for f in zf.namelist() if f.endswith(".xml")]
        if not xml_files:
            raise ValueError("No XML files found in zip archive")
        xml_filename = xml_files[0]
        zf.extract(xml_filename, output_path.parent)
        extracted = output_path.parent / xml_filename
        if extracted != output_path:
            extracted.rename(output_path)
        logger.info("Extracted XML to %s", output_path)
    return output_path


def _extract_text(element: etree._Element) -> str:
    """Recursively extract text content from an XML element."""
    return "".join(element.itertext()).strip()


def _parse_paragraph_number(enbez: str) -> str | None:
    """Extract paragraph number from enbez like '§ 535' or '§ 573a'.

    Returns the number part (e.g. '535', '573a') or None if not a paragraph.
    """
    match = re.match(r"§\s*(\d+[a-z]?)", enbez)
    return match.group(1) if match else None


def _is_in_mietrecht_range(paragraph: str, start: int = 535, end: int = 580) -> bool:
    """Check if a paragraph number falls within Mietrecht range.

    Handles suffixed paragraphs like '573a', '573c', '580a'.
    """
    num_match = re.match(r"(\d+)", paragraph)
    if not num_match:
        return False
    num = int(num_match.group(1))
    return start <= num <= end


def parse_bgb_xml(xml_path: Path, start: int = 535, end: int = 580) -> list[Norm]:
    """Parse BGB XML and extract Mietrecht norms.

    Args:
        xml_path: Path to the BGB XML file.
        start: First paragraph number (inclusive).
        end: Last paragraph base number (inclusive, includes suffixed variants like 580a).

    Returns:
        List of Norm objects for Mietrecht paragraphs.
    """
    logger.info("Parsing BGB XML from %s", xml_path)
    parser = etree.XMLParser(resolve_entities=False)
    tree = etree.parse(str(xml_path), parser=parser)
    root = tree.getroot()

    norms: list[Norm] = []

    # Try LegalDocML.de / akn namespace first
    articles = root.findall(".//akn:article", NAMESPACES)

    if articles:
        norms = _parse_akn_format(articles, start, end)
    else:
        # Fallback: try legacy BMJ format with <norm> elements
        norm_elements = root.findall(".//norm")
        if norm_elements:
            norms = _parse_legacy_format(norm_elements, start, end)
        else:
            # Try without namespace
            articles = root.findall(".//{*}article")
            if articles:
                norms = _parse_generic_articles(articles, start, end)
            else:
                logger.warning("No recognized format found in XML. Trying broad search...")
                norms = _parse_broad_search(root, start, end)

    logger.info("Extracted %d Mietrecht norms (§§%d-%da)", len(norms), start, end)
    return norms


def _parse_akn_format(articles: list[etree._Element], start: int, end: int) -> list[Norm]:
    """Parse LegalDocML.de (akn) format articles."""
    norms = []
    for article in articles:
        # Get paragraph identifier from heading/num
        num_el = article.find(".//akn:num", NAMESPACES)
        heading_el = article.find(".//akn:heading", NAMESPACES)

        if num_el is None:
            continue

        enbez = _extract_text(num_el)
        paragraph = _parse_paragraph_number(enbez)
        if not paragraph or not _is_in_mietrecht_range(paragraph, start, end):
            continue

        titel = _extract_text(heading_el) if heading_el is not None else ""

        # Extract body text from content/p elements
        content_parts = []
        for p_el in article.findall(".//akn:p", NAMESPACES):
            text = _extract_text(p_el)
            if text:
                content_parts.append(text)

        text = "\n".join(content_parts)
        if not text.strip():
            continue

        norm_id = f"bgb-{paragraph}"
        url = generate_norm_url("bgb", paragraph)

        norms.append(Norm(
            norm_id=norm_id,
            gesetz="BGB",
            paragraph=paragraph,
            titel=titel,
            text=text,
            url=url,
        ))

    return norms


def _parse_legacy_format(norm_elements: list[etree._Element], start: int, end: int) -> list[Norm]:
    """Parse legacy BMJ XML format with <norm> elements."""
    norms = []
    for norm_el in norm_elements:
        metadaten = norm_el.find(".//metadaten")
        if metadaten is None:
            continue

        enbez_el = metadaten.find("enbez")
        if enbez_el is None or enbez_el.text is None:
            continue

        paragraph = _parse_paragraph_number(enbez_el.text)
        if not paragraph or not _is_in_mietrecht_range(paragraph, start, end):
            continue

        titel_el = metadaten.find("titel")
        titel = titel_el.text.strip() if titel_el is not None and titel_el.text else ""

        # Extract text from textdaten/text/Content
        textdaten = norm_el.find(".//textdaten")
        if textdaten is None:
            continue

        content_el = textdaten.find(".//Content")
        if content_el is None:
            content_el = textdaten.find(".//text")

        if content_el is None:
            continue

        text = _extract_text(content_el)
        if not text.strip():
            continue

        norm_id = f"bgb-{paragraph}"
        url = generate_norm_url("bgb", paragraph)

        norms.append(Norm(
            norm_id=norm_id,
            gesetz="BGB",
            paragraph=paragraph,
            titel=titel,
            text=text,
            url=url,
        ))

    return norms


def _parse_generic_articles(articles: list[etree._Element], start: int, end: int) -> list[Norm]:
    """Parse articles with wildcard namespace matching."""
    norms = []
    for article in articles:
        # Find num and heading with any namespace
        num_el = article.find(".//{*}num")
        heading_el = article.find(".//{*}heading")

        if num_el is None:
            continue

        enbez = _extract_text(num_el)
        paragraph = _parse_paragraph_number(enbez)
        if not paragraph or not _is_in_mietrecht_range(paragraph, start, end):
            continue

        titel = _extract_text(heading_el) if heading_el is not None else ""

        content_parts = []
        for p_el in article.findall(".//{*}p"):
            text = _extract_text(p_el)
            if text:
                content_parts.append(text)

        text = "\n".join(content_parts)
        if not text.strip():
            continue

        norm_id = f"bgb-{paragraph}"
        url = generate_norm_url("bgb", paragraph)

        norms.append(Norm(
            norm_id=norm_id,
            gesetz="BGB",
            paragraph=paragraph,
            titel=titel,
            text=text,
            url=url,
        ))

    return norms


def _parse_broad_search(root: etree._Element, start: int, end: int) -> list[Norm]:
    """Last-resort: search for any element containing '§ NNN' patterns."""
    norms = []
    seen: set[str] = set()

    for el in root.iter():
        text = _extract_text(el)
        if not text:
            continue
        match = re.search(r"§\s*(\d+[a-z]?)", text)
        if not match:
            continue

        paragraph = match.group(1)
        norm_id = f"bgb-{paragraph}"

        if norm_id in seen or not _is_in_mietrecht_range(paragraph, start, end):
            continue

        # Only use elements with substantial text
        if len(text) < 50:
            continue

        seen.add(norm_id)
        url = generate_norm_url("bgb", paragraph)
        norms.append(Norm(
            norm_id=norm_id,
            gesetz="BGB",
            paragraph=paragraph,
            titel="",
            text=text,
            url=url,
        ))

    return norms
