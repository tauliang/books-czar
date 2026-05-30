from backend.manifest import parse_manifest_bytes


def test_parse_csv_manifest_with_urls():
    content = b"title,author,url,download_url\nAI Book,Jane,https://example.com/book,https://example.com/book.pdf\n"
    items = parse_manifest_bytes("books.csv", content)
    assert len(items) == 1
    assert items[0].title == "AI Book"
    assert items[0].download_url == "https://example.com/book.pdf"


def test_parse_json_manifest_object():
    content = b'{"books":[{"title":"Data Mesh","url":"https://example.com/catalog/data-mesh"}]}'
    items = parse_manifest_bytes("books.json", content)
    assert items[0].title == "Data Mesh"
    assert items[0].source_url == "https://example.com/catalog/data-mesh"
