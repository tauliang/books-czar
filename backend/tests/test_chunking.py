from backend.chunking import TextSection, chunk_sections, normalize_text


def test_normalize_text_collapses_extra_whitespace():
    assert normalize_text("one   two\n\n\nthree") == "one two\n\nthree"


def test_chunk_sections_respects_size_and_overlap():
    text = " ".join(f"word{i}." for i in range(300))
    chunks = chunk_sections([TextSection(location="chapter 1", text=text)], 300, 40)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 320 for chunk in chunks)
    assert {chunk.location for chunk in chunks} == {"chapter 1"}
