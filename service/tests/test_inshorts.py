import pytest
from tools.inshorts_provider import InshortsProvider


@pytest.mark.asyncio
async def test_inshorts_get_news_by_category():
    provider = InshortsProvider(timeout_seconds=8.0)
    articles = await provider.get_news_by_category("national", limit=5)
    assert isinstance(articles, list)
    if articles:
        first = articles[0]
        assert "title" in first
        assert "url" in first
        assert "source" in first
        assert "body" in first


@pytest.mark.asyncio
async def test_inshorts_search_news():
    provider = InshortsProvider(timeout_seconds=8.0)
    articles = await provider.search_news("reliance", limit=5)
    assert isinstance(articles, list)
    for a in articles:
        assert a.get("title")
        assert a.get("url")
        assert a.get("source")


@pytest.mark.asyncio
async def test_inshorts_normalization():
    provider = InshortsProvider()
    raw = {
        "title": "Test Title",
        "content": "Test short 60-word content.",
        "author_name": "Reporter",
        "source_name": "Test Publication",
        "source_url": "https://example.com/article",
        "shortened_url": "http://shrts.in/abc",
        "created_at": 1700000000000,
        "image_url": "https://example.com/image.jpg"
    }
    norm = provider._normalize_entry(raw)
    assert norm is not None
    assert norm["title"] == "Test Title"
    assert norm["url"] == "https://example.com/article"
    assert norm["publisher"] == "Test Publication"
    assert norm["body"] == "Test short 60-word content."
    assert "2023" in norm["published_at"]

