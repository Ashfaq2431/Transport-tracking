from datetime import datetime
from backend.app.scrapers.tn_transport import TNTransportAdapter
from backend.app.services.refresh import _adapter
from backend.app.models import Source


def test_tn_transport_adapter_parses_mtc_announcements():
    html_sample = """
    <div class="news-list">
        <article class="news-item">
            <h3>Broadway Bus Terminus Temporarily Shifted to Island Grounds and Royapuram</h3>
            <p class="summary">Due to modernization at Broadway Bus Stand, MTC routes 11G, 102, 21G, and 570 are relocated.</p>
            <time>2026-11-03</time>
            <a href="https://mtcbus.tn.gov.in/news/broadway">Read more</a>
        </article>
    </div>
    """
    adapter = TNTransportAdapter("https://mtcbus.tn.gov.in/Home/news")
    notices = adapter.parse(html_sample)

    assert len(notices) == 1
    notice = notices[0]
    assert "Broadway" in notice.title
    assert "11G" in notice.route_ids
    assert "102" in notice.route_ids
    assert "570" in notice.route_ids
    assert notice.advisory_type == "route diversion"
    assert notice.area == "Broadway"


def test_tn_transport_adapter_parses_southern_railway_table():
    railway_html = """
    <table class="table">
        <tr><th>Date</th><th>PR No</th><th>Subject</th><th>Link</th></tr>
        <tr>
            <td>03-11-2026</td>
            <td>PR-MAS-2026-89</td>
            <td>Mega Line Block between Chennai Beach and Tambaram: Suburban EMU Regulation for Third Line Works</td>
            <td><a href="https://sr.indianrailways.gov.in/pr89.pdf">Download PR</a></td>
        </tr>
    </table>
    """
    adapter = TNTransportAdapter("https://sr.indianrailways.gov.in/press_releases.html")
    notices = adapter.parse(railway_html)

    assert len(notices) == 1
    notice = notices[0]
    assert "Mega Line Block" in notice.title
    assert "EMU-SUBURBAN" in notice.route_ids or "MSB-TBM" in notice.route_ids
    assert notice.advisory_type == "planned maintenance"
    assert "Chennai Beach - Tambaram" in notice.area


def test_tn_transport_adapter_parses_cmrl_metro_notices():
    cmrl_html = """
    <div class="press-release">
        <h2>Metro Rail Timings Extended up to 23:30 for Blue Line and Green Line Commuters</h2>
        <p>Chennai Metro announces enhanced frequency between Airport and Central Metro.</p>
        <time>2026-11-03</time>
    </div>
    """
    adapter = TNTransportAdapter("https://chennaimetrorail.org")
    notices = adapter.parse(cmrl_html)

    assert len(notices) == 1
    notice = notices[0]
    assert "BLUE LINE" in notice.route_ids
    assert "GREEN LINE" in notice.route_ids
    assert notice.advisory_type == "service update"


def test_refresh_service_resolves_tn_and_railway_adapters():
    s_mtc = Source(source_name="MTC", source_url="https://mtcbus.tn.gov.in", source_type="tn_transport")
    s_rail = Source(source_name="Southern Railway", source_url="https://sr.indianrailways.gov.in", source_type="railways")
    s_html = Source(source_name="Generic HTML", source_url="https://example.com", source_type="html")

    assert isinstance(_adapter(s_mtc), TNTransportAdapter)
    assert isinstance(_adapter(s_rail), TNTransportAdapter)
    assert isinstance(_adapter(s_html), TNTransportAdapter)

