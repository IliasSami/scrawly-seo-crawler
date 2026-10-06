"""Download headers survive Unicode (IDN) file names: HTTP headers are latin-1,
so a report for bücher.de used to crash after the PDF was already rendered."""
import sentinelseo.web.api as api


def test_ascii_name_is_unchanged() -> None:
    assert api._attachment_header("scrawly-report-example.com.pdf") == \
        'attachment; filename="scrawly-report-example.com.pdf"'


def test_unicode_name_gets_ascii_fallback_and_rfc5987() -> None:
    h = api._attachment_header("scrawly-report-bücher.de.pdf")
    h.encode("latin-1")   # must be encodable as an HTTP header
    assert 'filename="scrawly-report-bcher.de.pdf"' in h
    assert "filename*=UTF-8''scrawly-report-b%C3%BCcher.de.pdf" in h


def test_quotes_cannot_break_the_header() -> None:
    h = api._attachment_header('a"b-ü.pdf')
    assert h.count('"') == 2
