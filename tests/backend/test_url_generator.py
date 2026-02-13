"""Tests for URL generation."""

from postprocessing.url_generator import generate_norm_url


def test_basic_paragraph():
    url = generate_norm_url("bgb", "535")
    assert url == "https://www.gesetze-im-internet.de/bgb/__535.html"


def test_suffixed_paragraph():
    url = generate_norm_url("bgb", "573a")
    assert url == "https://www.gesetze-im-internet.de/bgb/__573a.html"


def test_uppercase_gesetz():
    url = generate_norm_url("BGB", "556")
    assert url == "https://www.gesetze-im-internet.de/bgb/__556.html"


def test_paragraph_with_section_symbol():
    url = generate_norm_url("bgb", "§ 535")
    assert url == "https://www.gesetze-im-internet.de/bgb/__535.html"


def test_paragraph_580a():
    url = generate_norm_url("bgb", "580a")
    assert url == "https://www.gesetze-im-internet.de/bgb/__580a.html"
