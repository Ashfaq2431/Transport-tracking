from bs4 import BeautifulSoup

from .base import SourceAdapter
from .normalize import (
    clean_text,
    normalize_advisory_type,
    normalize_route_ids,
    parse_datetime,
)
from .schemas import NormalizedNotice


class HtmlNoticeAdapter(SourceAdapter):
    """Parse configured notice cards from an approved HTML source."""

    def parse(self, body: str, response_url: str | None = None) -> list[NormalizedNotice]:
        soup = BeautifulSoup(body, "html.parser")
        notices: list[NormalizedNotice] = []
        for card in soup.select("[data-transit-notice]"):
            title_node = card.select_one("[data-field='title']")
            title = clean_text(title_node.get_text(" ", strip=True)) if title_node else None
            if title is None:
                heading = card.select_one("h2, h3")
                title = clean_text(heading.get_text(" ", strip=True)) if heading else None
            if title is None:
                continue

            def text(field: str) -> str | None:
                node = card.select_one(f"[data-field='{field}']")
                return clean_text(node.get_text(" ", strip=True)) if node else None

            link = card.select_one("[data-field='source-url']") or card.select_one("a[href]")
            source_url = link.get("href") if link else response_url or self.source_url
            return_url = source_url.strip() if source_url else None
            notices.append(
                NormalizedNotice(
                    external_notice_id=card.get("data-notice-id"),
                    title=title,
                    summary=text("summary"),
                    full_text=text("full-text") or text("summary"),
                    route_ids=normalize_route_ids(text("routes")),
                    area=text("area"),
                    advisory_type=normalize_advisory_type(text("type")),
                    source_url=return_url,
                    published_at=parse_datetime(text("published")),
                    valid_from=parse_datetime(text("valid-from")),
                    valid_to=parse_datetime(text("valid-to")),
                    withdrawn=(text("status") or "").lower() in {"withdrawn", "cancelled"},
                )
            )
        return notices
