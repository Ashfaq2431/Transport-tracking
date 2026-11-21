import feedparser

from .base import SourceAdapter
from .normalize import (
    clean_text,
    normalize_advisory_type,
    normalize_route_ids,
    parse_datetime,
)
from .schemas import NormalizedNotice


class RssNoticeAdapter(SourceAdapter):
    """Parse RSS or Atom entries from an approved feed."""

    def parse(self, body: str, response_url: str | None = None) -> list[NormalizedNotice]:
        parsed = feedparser.parse(body)
        notices: list[NormalizedNotice] = []
        for entry in parsed.entries:
            title = clean_text(entry.get("title"))
            if not title:
                continue
            description = clean_text(entry.get("summary") or entry.get("description"))
            source_url = clean_text(entry.get("link")) or response_url or self.source_url
            notices.append(
                NormalizedNotice(
                    external_notice_id=clean_text(entry.get("id") or entry.get("guid")),
                    title=title,
                    summary=description,
                    full_text=description,
                    route_ids=normalize_route_ids(entry.get("route") or entry.get("routes")),
                    area=clean_text(entry.get("area")),
                    advisory_type=normalize_advisory_type(entry.get("type")),
                    source_url=source_url,
                    published_at=parse_datetime(entry.get("published") or entry.get("updated")),
                    valid_from=parse_datetime(entry.get("valid_from")),
                    valid_to=parse_datetime(entry.get("valid_to")),
                    withdrawn=(clean_text(entry.get("status")) or "").lower()
                    in {"withdrawn", "cancelled"},
                )
            )
        return notices

