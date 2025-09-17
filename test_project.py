import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from project import fetch_page_source, summarize_news, translate, fetch_daily_news, fetch_news_content, verify_hour, verify_timezone, News

# Helper to run async functions in tests
def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

# Test for verify_hour
@pytest.mark.parametrize("hour, expected", [
    ("00:00", True),
    ("23:59", True),
    ("12:30", True),
    ("24:00", False),
    ("1:60", False),
    ("abc", False),
    ("", False),
])
def test_verify_hour(hour, expected):
    assert run_async(verify_hour(hour)) == expected

# Test for verify_timezone
@pytest.mark.parametrize("timezone, expected", [
    ("Etc/UTC", True),
    ("Etc/GMT+0", True),
    ("Etc/GMT-14", True),
    ("Etc/GMT+14", True),
    ("Etc/GMT", False),  # Missing sign and number
    ("America/Sao_Paulo", False),  # Invalid format
    ("Etc/UTC+1", False),  # Invalid format
    ("", False),
])
def test_verify_timezone(timezone, expected):
    assert run_async(verify_timezone(timezone)) == expected

# Mock HTML for HLTV homepage
MOCK_HLTV_HTML = """
<html>
<body>
<a class="newsline article" href="/news/12345/test-news">
    <div class="newsrecent">1 hour ago</div>
    <div class="newstext">Test Title</div>
    <div class="newstc">
        <div>10 comments</div>
    </div>
</a>
<a class="newsline article" href="/news/67890/old-news">
    <div class="newsrecent">2 days ago</div>
    <div class="newstext">Old Title</div>
    <div class="newstc">
        <div>5 comments</div>
    </div>
</a>
</body>
</html>
"""

# Mock HTML for news content
MOCK_NEWS_CONTENT_HTML = """
<html>
<body>
<div class="newstext-con">This is the news content.</div>
<img class="image" src="https://example.com/image.jpg">
</body>
</html>
"""

# Test fetch_page_source with mock
@patch('project.webdriver.Chrome')
def test_fetch_page_source(mock_chrome):
    mock_driver = MagicMock()
    mock_chrome.return_value = mock_driver
    mock_driver.page_source = MOCK_HLTV_HTML

    result = run_async(fetch_page_source("https://www.hltv.org"))
    assert result == MOCK_HLTV_HTML

# Test fetch_daily_news with mock fetch_page_source
@patch('project.fetch_page_source', return_value=MOCK_HLTV_HTML)
def test_fetch_daily_news(mock_fetch):
    news_list = run_async(fetch_daily_news())
    assert len(news_list) == 1  # Only recent news
    assert news_list[0].title == "Test Title"
    assert news_list[0].url == "https://www.hltv.org/news/12345/test-news"
    assert news_list[0].comments == 10

# Test fetch_news_content with mock fetch_page_source
@patch('project.fetch_page_source', return_value=MOCK_NEWS_CONTENT_HTML)
def test_fetch_news_content(mock_fetch):
    news = News(title="Test", url="https://www.hltv.org/news/12345/test-news")
    content = run_async(fetch_news_content(news))
    assert content == "This is the news content."
    assert news.img == "https://example.com/image.jpg"

# Test translate with mock client
@patch('project.client')
def test_translate(mock_client):
    # Set up the mock to return a response with output_text
    mock_response = MagicMock()
    mock_response.output_text = "Mocked output"
    mock_client.responses.create = AsyncMock(return_value=mock_response)

    result = run_async(translate("Test text", mock_client))
    assert result == "Mocked output"

# Test summarize_news with mock client
@patch('project.client')
def test_summarize_news(mock_client):
    # Set up the mock to return a response with output_text
    mock_response = MagicMock()
    mock_response.output_text = "Mocked output"
    mock_client.responses.create = AsyncMock(return_value=mock_response)

    result = run_async(summarize_news("Long content here", mock_client))
    assert result == "Mocked output"

# Test summarize_news with empty content
def test_summarize_news_empty():
    result = run_async(summarize_news("", None))
    assert result == ""

# Test translate with empty text
def test_translate_empty():
    result = run_async(translate("", None))
    assert result == ""