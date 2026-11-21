import re
from datetime import datetime
from bs4 import BeautifulSoup

from .base import SourceAdapter
from .normalize import (
    clean_text,
    normalize_advisory_type,
    normalize_route_ids,
    parse_datetime,
)
from .schemas import NormalizedNotice


class TNTransportAdapter(SourceAdapter):
    """Scraper adapter for Tamil Nadu Transport services (TNSTC, MTC, SETC, CMRL)
    and Southern Railway (SR) advisories and service updates.
    """

    def parse(self, body: str, response_url: str | None = None) -> list[NormalizedNotice]:
        soup = BeautifulSoup(body, "html.parser")
        notices: list[NormalizedNotice] = []

        # 1. Backwards compatibility: Check for standard [data-transit-notice] cards
        custom_cards = soup.select("[data-transit-notice]")
        if custom_cards:
            for card in custom_cards:
                notice = self._parse_custom_card(card, response_url)
                if notice:
                    notices.append(notice)
            if notices:
                return notices

        # 2. Southern Railway (Indian Railways) press release table format
        # Common structure: <table> with columns [Date, PR No / Subject, Details / Link]
        sr_rows = soup.select("table.table tr, table tr")
        table_notices = self._parse_table_rows(sr_rows, response_url)
        if table_notices:
            return table_notices

        # 3. MTC / CMRL / News & Announcements list items or article cards
        announcement_items = soup.select(
            ".news-item, .press-release, .notice-item, .card, article, "
            ".view-content .views-row, ul.news-list li, ul.announcements li"
        )
        for item in announcement_items:
            notice = self._parse_announcement_item(item, response_url)
            if notice:
                notices.append(notice)

        return notices

    def _parse_custom_card(self, card, response_url: str | None) -> NormalizedNotice | None:
        title_node = card.select_one("[data-field='title']")
        title = clean_text(title_node.get_text(" ", strip=True)) if title_node else None
        if title is None:
            heading = card.select_one("h2, h3, h4")
            title = clean_text(heading.get_text(" ", strip=True)) if heading else None
        if title is None:
            return None

        def text(field: str) -> str | None:
            node = card.select_one(f"[data-field='{field}']")
            return clean_text(node.get_text(" ", strip=True)) if node else None

        link = card.select_one("[data-field='source-url']") or card.select_one("a[href]")
        source_url = link.get("href") if link else response_url or self.source_url
        return_url = source_url.strip() if source_url else None

        return NormalizedNotice(
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

    def _parse_table_rows(self, rows, response_url: str | None) -> list[NormalizedNotice]:
        notices: list[NormalizedNotice] = []
        for idx, row in enumerate(rows):
            cols = row.select("td")
            if len(cols) < 2:
                continue

            col_texts = [clean_text(td.get_text(" ", strip=True)) or "" for td in cols]
            # Try to identify date and headline
            date_val = None
            title_val = None
            pr_id = None
            link_url = None

            for col, td in zip(col_texts, cols):
                link = td.select_one("a[href]")
                if link and not link_url:
                    link_url = link.get("href")
                parsed_dt = parse_datetime(col)
                if parsed_dt and not date_val:
                    date_val = parsed_dt
                elif len(col) > 15 and not title_val:
                    title_val = col
                elif re.match(r"^[A-Z0-9_\-\/]{3,20}$", col) and not pr_id:
                    pr_id = col

            if not title_val and len(col_texts) >= 2:
                # Fallback to the longest column text
                longest = max(col_texts, key=len)
                if len(longest) > 10:
                    title_val = longest

            if not title_val:
                continue

            routes = self._extract_routes(title_val)
            area = self._extract_area(title_val)
            adv_type = self._classify_advisory_type(title_val)

            notices.append(
                NormalizedNotice(
                    external_notice_id=pr_id or f"tn-row-{idx}",
                    title=title_val,
                    summary=title_val,
                    full_text=title_val,
                    route_ids=routes,
                    area=area,
                    advisory_type=adv_type,
                    source_url=link_url or response_url or self.source_url,
                    published_at=date_val or datetime.utcnow(),
                    valid_from=date_val or datetime.utcnow(),
                    valid_to=None,
                    withdrawn="cancelled" in title_val.lower(),
                )
            )
        return notices

    def _parse_announcement_item(self, item, response_url: str | None) -> NormalizedNotice | None:
        heading = item.select_one("h2, h3, h4, .title, strong, a")
        title = clean_text(heading.get_text(" ", strip=True)) if heading else clean_text(item.get_text(" ", strip=True))
        if not title or len(title) < 10:
            return None

        summary_node = item.select_one("p, .desc, .summary, .content")
        summary = clean_text(summary_node.get_text(" ", strip=True)) if summary_node else title

        link_node = item.select_one("a[href]")
        source_url = link_node.get("href") if link_node else response_url or self.source_url

        time_node = item.select_one("time, .date, span.created, small")
        time_text = clean_text(time_node.get_text(" ", strip=True)) if time_node else None
        published_at = parse_datetime(time_text) if time_text else None

        routes = self._extract_routes(f"{title} {summary}")
        area = self._extract_area(f"{title} {summary}")
        adv_type = self._classify_advisory_type(f"{title} {summary}")

        return NormalizedNotice(
            external_notice_id=item.get("id") or item.get("data-id") or None,
            title=title,
            summary=summary,
            full_text=summary,
            route_ids=routes,
            area=area,
            advisory_type=adv_type,
            source_url=source_url,
            published_at=published_at,
            valid_from=published_at,
            valid_to=None,
            withdrawn=any(w in title.lower() for w in ["cancelled", "withdrawn", "suspended"]),
        )

    def _extract_routes(self, text: str) -> list[str]:
        routes: set[str] = set()
        # Bus patterns: 29C, 102, 570, 21G, 11G, 70V, M1, D70, etc.
        bus_matches = re.findall(r"\b(?:Route|Bus|No\.?)\s*([0-9]{1,3}[A-Z]{0,2}|[A-Z]{1,2}[0-9]{1,3})\b", text, re.IGNORECASE)
        routes.update(m.upper() for m in bus_matches)

        # Standalone common routes in Tamil Nadu
        specific_routes = re.findall(r"\b(29C|102|570|21G|11G|70C|70V|500|19B|A1|D70|M1|17D|114)\b", text, re.IGNORECASE)
        routes.update(m.upper() for m in specific_routes)

        # Metro lines: Blue Line, Green Line, Corridor 3, Corridor 4, Corridor 5
        if re.search(r"blue\s*line", text, re.IGNORECASE):
            routes.add("BLUE LINE")
        if re.search(r"green\s*line", text, re.IGNORECASE):
            routes.add("GREEN LINE")
        metro_corridors = re.findall(r"\bCorridor[-\s]*([0-9])\b", text, re.IGNORECASE)
        for c in metro_corridors:
            routes.add(f"CORRIDOR-{c}")

        # Railways: EMU, MSB-TBM, MAS-AJJ, Train numbers (e.g. Train 12635)
        train_matches = re.findall(r"\b(?:Train\s*(?:No\.?)?\s*([0-9]{5}))\b", text, re.IGNORECASE)
        routes.update(f"TR-{m}" for m in train_matches)
        if re.search(r"\b(?:EMU|Suburban)\b", text, re.IGNORECASE):
            routes.add("EMU-SUBURBAN")
        if re.search(r"\b(?:Chennai Beach|Tambaram|Chengalpattu)\b", text, re.IGNORECASE):
            routes.add("MSB-TBM")
        if re.search(r"\b(?:Arakkonam|Tiruvallur|Central)\b", text, re.IGNORECASE):
            routes.add("MAS-AJJ")

        return sorted(routes)

    def _extract_area(self, text: str) -> str:
        areas = [
            "Chennai Beach - Tambaram",
            "Chennai Central - Arakkonam",
            "Broadway",
            "Island Grounds",
            "Royapuram",
            "Kilambakkam (KCBT)",
            "Koyambedu (CMBT)",
            "Madhavaram",
            "Tambaram",
            "Guindy",
            "OMR / Sholinganallur",
            "Tiruvallur",
            "Chengalpattu",
            "Coimbatore",
            "Madurai",
            "Salem",
            "Tiruchirappalli",
            "Tirunelveli",
            "Kumbakonam",
            "Vellore",
            "Erode",
        ]
        for area in areas:
            if re.search(r"\b" + re.escape(area.split(" ")[0]) + r"\b", text, re.IGNORECASE):
                return area
        return "Tamil Nadu Transport Network"

    def _classify_advisory_type(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["divert", "diversion", "shifted", "relocated", "rerouted"]):
            return "route diversion"
        if any(w in text_lower for w in ["line block", "power block", "maintenance", "engineering work"]):
            return "planned maintenance"
        if any(w in text_lower for w in ["suspend", "suspended", "cancel", "cancelled", "struck off"]):
            return "service suspension"
        if any(w in text_lower for w in ["delay", "delayed", "late", "regulated", "regulation", "slow"]):
            return "delay"
        if any(w in text_lower for w in ["special bus", "special train", "festival special", "pongal", "deepavali", "additional bus"]):
            return "special service"
        if any(w in text_lower for w in ["new service", "inaugurate", "extension", "extended", "feeder"]):
            return "service update"
        return "general service update"

