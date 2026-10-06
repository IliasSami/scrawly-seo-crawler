from sentinelseo.crawl.parser import parse_html


def test_parse_clean_page() -> None:
    with open("tests/fixtures/clean_page.html", "r") as f:
        html = f.read()

    url_row, images, sds = parse_html("http://localhost:8080/clean", html)

    assert url_row.title == "Clean Page Title"
    assert url_row.meta_desc == "A very clean page with good SEO."
    assert url_row.canonical == "http://localhost:8080/clean"
    assert "Welcome to the Clean Page" in url_row.h1
    assert url_row.word_count > 10

    assert len(images) == 1
    assert images[0].src == "http://localhost:8080/image.png"
    assert images[0].alt == "A nice image"

    assert len(sds) == 0


def test_parse_missing_title() -> None:
    with open("tests/fixtures/missing_title.html", "r") as f:
        html = f.read()

    url_row, images, sds = parse_html("http://localhost:8080/missing-title", html)

    assert url_row.title is None


def test_parse_invalid_jsonld() -> None:
    with open("tests/fixtures/invalid_jsonld.html", "r") as f:
        html = f.read()

    url_row, images, sds = parse_html("http://localhost:8080/invalid-jsonld", html)

    assert len(sds) == 1
    assert sds[0].valid is False
