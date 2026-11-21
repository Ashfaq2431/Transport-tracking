# TransitNotice backend

The backend provides the FastAPI application, MySQL persistence, modular
scrapers, refresh scheduler, advisory search and pagination, revision history,
source freshness monitoring, in-app notifications, analytics, and CSV export.

Run from the project root:

```powershell
python -m uvicorn backend.app.main:app --reload
```

The API documentation is available at `http://localhost:8000/docs`.

Useful endpoints include:

- `GET /api/advisories` for combined search, filters, sorting, and pagination.
- `GET /api/advisories/{notice_id}/history` for revision comparisons.
- `GET /api/sources/health` and `GET /api/refresh-runs` for source monitoring.
- `GET /api/alerts` plus the read endpoints for in-app notifications.
- `GET /api/analytics/summary` for backend-derived aggregates.
- `GET /api/advisories/export.csv` for filtered CSV downloads.

After changing an existing database, apply migrations with:

```powershell
python -m alembic upgrade head
```
