"""M4 extraction depth: Flesch readability + text-to-code + forms in parse_html."""
from sentinelseo.crawl.parser import flesch_reading_ease, parse_html


def test_flesch_easy_vs_hard() -> None:
    easy = "The cat sat on the mat. The dog ran. It was fun."
    hard = (
        "Notwithstanding the aforementioned considerations, the multifarious "
        "ramifications of the epistemological framework necessitate "
        "comprehensive reconceptualization."
    )
    e = flesch_reading_ease(easy)
    h = flesch_reading_ease(hard)
    assert e is not None and h is not None
    assert e > h  # simple sentences score higher than dense ones


def test_flesch_empty() -> None:
    assert flesch_reading_ease("") is None
    assert flesch_reading_ease("   ") is None


def test_parse_extracts_new_signals() -> None:
    html = (
        "<html><body>"
        "<p>The cat sat on the mat. The dog ran fast. It was a fun day.</p>"
        "<form><input name='q'></form><form><input name='x'></form>"
        "</body></html>"
    )
    row, _imgs, _sd = parse_html("https://x.com/", html)
    assert row.forms_count == 2
    assert row.readability is not None
    assert row.text_to_code is not None
    assert 0.0 <= row.text_to_code <= 1.0
