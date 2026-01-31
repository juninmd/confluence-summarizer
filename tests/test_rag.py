from confluence_refiner.services.rag import chunk_text


def test_chunk_text_simple():
    text = "Hello world this is a test"
    chunks = chunk_text(text, chunk_size=11, overlap=0)
    # "Hello world" is 11 chars. " this is a "
    # Expect split at space
    assert "Hello world" in chunks or "Hello" in chunks


def test_chunk_text_long_word():
    text = "A" * 20
    chunks = chunk_text(text, chunk_size=10, overlap=0)
    assert len(chunks) == 2
    assert chunks[0] == "A" * 10


def test_chunk_text_overlap():
    text = "one two three four"
    # chunk size 10. "one two th" -> split at space -> "one two"
    # overlap ?
    chunks = chunk_text(text, chunk_size=8, overlap=2)
    # 0-8: "one two " -> rfind space -> 7 ("one two")
    # chunk 1: "one two"
    # next start: 7 - 2 = 5. text[5:] = "wo three four"... wait.
    # text indices:
    # 012345678901234567
    # one two three four
    # Chunk 1: "one two" (end=7).
    # Next start = 7 - 2 = 5. text[5] = 'w'.
    # text[5:13] = "wo three"
    # ...
    assert len(chunks) > 0
    assert "one two" in chunks
