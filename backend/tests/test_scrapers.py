from pathlib import Path

from backend.app.scrapers.html import HtmlNoticeAdapter
from backend.app.scrapers.normalize import content_hash, parse_datetime
from backend.app.scrapers.rss import RssNoticeAdapter


FIXTURES = Path(__file__).parents[2] / "fixtures"


def test_html_adapter_normalizes_notice_and_timezone():
    body = (FIXTURES / "sample_notices.html").read_text(encoding="utf-8")

    notices = HtmlNoticeAdapter("https://example.invalid/feed").parse(body)

    assert len(notices) == 1
    assert notices[0].route_ids == ["10", "20"]
    assert notices[0].advisory_type == "delay"
    assert notices[0].published_at.isoformat() == "2026-11-03T02:30:00+00:00"


def test_rss_adapter_parses_feed_entries():
    body = (FIXTURES / "sample_notices.rss").read_text(encoding="utf-8")

    notices = RssNoticeAdapter("https://example.invalid/feed").parse(body)

    assert len(notices) == 1
    assert notices[0].external_notice_id == "rss-001"
    assert notices[0].route_ids == ["10", "20"]
    assert notices[0].source_url == "https://example.invalid/notices/rss-001"


def test_malformed_html_and_missing_values_are_safe():
    notices = HtmlNoticeAdapter("https://example.invalid/feed").parse(
        "<article data-transit-notice><p>No title</p>"
    )

    assert notices == []


def test_missing_dates_and_routes_are_represented_as_unknown():
    notices = RssNoticeAdapter("https://example.invalid/feed").parse(
        "<rss><channel><item><title>Notice</title></item></channel></rss>"
    )

    assert notices[0].route_ids == []
    assert notices[0].published_at is None
    assert notices[0].valid_to is None


def test_naive_source_timestamp_is_documented_as_utc():
    assert parse_datetime("2026-11-03 10:00").isoformat() == "2026-11-03T10:00:00+00:00"
    assert content_hash("same", "content") == content_hash("same", "content")
