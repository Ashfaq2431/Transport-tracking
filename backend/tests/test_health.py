from sqlalchemy.exc import SQLAlchemyError

from backend.app.main import health_check, root


def test_health_endpoint_reports_api_when_database_is_unavailable(monkeypatch):
    class FailedEngine:
        def connect(self):
            raise SQLAlchemyError("database is intentionally unavailable")

    monkeypatch.setattr("backend.app.main.engine", FailedEngine())

    result = health_check()
    assert result == {
        "status": "degraded",
        "service": "tn-transit-tracker-api",
        "database": "unavailable",
    }


def test_root_endpoint_points_to_documentation():
    result = root()
    assert result["docs"] == "/docs"
