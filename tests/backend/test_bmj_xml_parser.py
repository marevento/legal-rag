"""Tests for BMJ XML parser."""

from pathlib import Path

from prepdocslib.bmj_xml_parser import (
    _is_in_mietrecht_range,
    _parse_paragraph_number,
    parse_bgb_xml,
)


def test_parse_paragraph_number():
    assert _parse_paragraph_number("§ 535") == "535"
    assert _parse_paragraph_number("§ 573a") == "573a"
    assert _parse_paragraph_number("§535") == "535"
    assert _parse_paragraph_number("§ 580a") == "580a"
    assert _parse_paragraph_number("Art. 1") is None
    assert _parse_paragraph_number("") is None


def test_is_in_mietrecht_range():
    assert _is_in_mietrecht_range("535") is True
    assert _is_in_mietrecht_range("556") is True
    assert _is_in_mietrecht_range("573a") is True
    assert _is_in_mietrecht_range("580") is True
    assert _is_in_mietrecht_range("580a") is True
    assert _is_in_mietrecht_range("534") is False
    assert _is_in_mietrecht_range("581") is False
    assert _is_in_mietrecht_range("1") is False


def test_parse_legacy_format(tmp_path: Path):
    """Test parsing legacy BMJ XML format with <norm> elements."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<dokumente>
  <norm>
    <metadaten>
      <enbez>§ 535</enbez>
      <titel>Inhalt und Hauptpflichten des Mietvertrags</titel>
    </metadaten>
    <textdaten>
      <text>
        <Content>
          <P>(1) Durch den Mietvertrag wird der Vermieter verpflichtet, dem Mieter den Gebrauch der Mietsache während der Mietzeit zu gewähren.</P>
        </Content>
      </text>
    </textdaten>
  </norm>
  <norm>
    <metadaten>
      <enbez>§ 1</enbez>
      <titel>Beginn der Rechtsfähigkeit</titel>
    </metadaten>
    <textdaten>
      <text>
        <Content>
          <P>Die Rechtsfähigkeit des Menschen beginnt mit der Vollendung der Geburt.</P>
        </Content>
      </text>
    </textdaten>
  </norm>
  <norm>
    <metadaten>
      <enbez>§ 556</enbez>
      <titel>Vereinbarungen über Betriebskosten</titel>
    </metadaten>
    <textdaten>
      <text>
        <Content>
          <P>(1) Die Vertragsparteien können vereinbaren, dass der Mieter Betriebskosten trägt.</P>
        </Content>
      </text>
    </textdaten>
  </norm>
</dokumente>"""

    xml_file = tmp_path / "test.xml"
    xml_file.write_text(xml_content, encoding="utf-8")
    norms = parse_bgb_xml(xml_file)

    # Should only include Mietrecht paragraphs
    assert len(norms) == 2
    assert norms[0].paragraph == "535"
    assert norms[1].paragraph == "556"
    assert norms[0].titel == "Inhalt und Hauptpflichten des Mietvertrags"
    assert "Mietvertrag" in norms[0].text
    assert norms[0].url == "https://www.gesetze-im-internet.de/bgb/__535.html"


def test_parse_empty_xml(tmp_path: Path):
    """Test parsing XML with no matching norms."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<dokumente>
  <norm>
    <metadaten>
      <enbez>§ 1</enbez>
      <titel>Test</titel>
    </metadaten>
    <textdaten>
      <text><Content><P>Test text.</P></Content></text>
    </textdaten>
  </norm>
</dokumente>"""

    xml_file = tmp_path / "test_empty.xml"
    xml_file.write_text(xml_content, encoding="utf-8")
    norms = parse_bgb_xml(xml_file)

    assert len(norms) == 0
