# TN Transport & Railway Tracker

TN Transport & Railway Tracker is a comprehensive public transport and railway
service update tracker tailored for Tamil Nadu. It monitors official advisories,
terminal shifting notices, line blocks, festival special operations, and route
diversions across Tamil Nadu bus networks, Chennai Metro, and Southern Railway.

## Covered Authorities & Networks

- **TNSTC:** Tamil Nadu State Transport Corporation (intercity mofussil buses & festival specials)
- **MTC Chennai:** Metropolitan Transport Corporation (city bus services, Broadway/Kilambakkam diversions)
- **SETC:** State Express Transport Corporation (long-distance express & AC sleeper operations)
- **CMRL:** Chennai Metro Rail Limited (Blue & Green line schedules, feeder mini-buses)
- **Southern Railway (SR):** Chennai Suburban EMU trains & mainline line blocks / maintenance

## Architecture Overview

- **Frontend:** React with Vite, JavaScript, responsive modern CSS dashboard.
  - Branded for Tamil Nadu State Control Center.
  - Administrator: **Ashfaq Ahamed J**
  - Active User / Operator: **Venkat**
- **Backend:** FastAPI REST API with modular services, source adapters, and scheduler.
- **Database:** MySQL accessed through SQLAlchemy ORM and Alembic migrations.
- **Scrapers:** Dedicated `TNTransportAdapter` parsing official MTC, CMRL, TNSTC, and Southern Railway updates.
- **Testing:** Pytest for backend behavior, models, and scraper parsing.

## Folder Structure

```text
TransitNotice/
├── backend/
│   ├── app/
│   │   ├── routers/        # FastAPI endpoints (/api/advisories, /api/sources, /api/dashboard)
│   │   ├── services/       # Refresh pipeline, scheduler, status calculators
│   │   ├── scrapers/       # TNTransportAdapter, HtmlNoticeAdapter, RssNoticeAdapter
│   │   ├── config.py       # Pydantic settings
│   │   ├── database.py     # SQLAlchemy engine & session factory
│   │   ├── models.py       # Database schema models
│   │   └── main.py         # App factory & lifespan hooks
│   ├── tests/              # Pytest suite
│   ├── seed.py             # Seeds TNSTC, MTC, SETC, CMRL & Southern Railway
│   └── scrape_tn.py        # Live scraper CLI script
├── frontend/               # React + Vite dashboard
├── alembic/                # Database migrations
├── fixtures/               # Sample HTML/RSS test feeds
├── .env.example
├── requirements.txt
└── README.md
```

## Setup & Execution

1. Create and activate a Python virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Ensure `.env` is configured with your MySQL connection:

   ```env
   APP_NAME=Tamil Nadu Transport & Railway Advisory API
   APP_ENV=development
   API_PREFIX=/api
   DATABASE_URL=mysql+pymysql://root:Ashfaq%402007@localhost:3306/transitnotice
   FRONTEND_ORIGIN=http://localhost:5173
   ```

4. Run database migrations:

   ```powershell
   python -m alembic upgrade head
   ```

5. Seed Tamil Nadu transport agencies, sources, and initial advisories:

   ```powershell
   python backend\seed.py
   ```

6. Run live scraper to check and fetch updates:

   ```powershell
   python backend\scrape_tn.py
   ```

7. Run tests:

   ```powershell
   python -m pytest backend\tests
   ```

8. Start the backend API:

   ```powershell
   python -m uvicorn backend.app.main:app --reload
   ```

9. Start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

Open `http://localhost:5173` to explore the dashboard.

## Backend API

The advisory list supports full-text search (`search`), status/area/type/route,
source and agency filters, published date bounds, deterministic sorting
(`sort_by` and `sort_order`), and bounded pagination.  The CSV download is
available at `GET /api/advisories/export.csv`.

Operational endpoints include `GET /api/sources/health` for freshness state and
`GET /api/refresh-runs` for refresh history.  Revision history is paginated at
`GET /api/advisories/{notice_id}/history`.  In-app alerts can be filtered with
`unread_only=true`, marked individually with `POST /api/alerts/{alert_id}/read`,
or marked in bulk with `POST /api/alerts/read-all`; the existing revision/event
unique constraint prevents duplicate notifications.  `GET /api/analytics/summary`
returns status, type, source, revision, and unread-alert aggregates.

After upgrading an existing database, run `python -m alembic upgrade head` to
apply the notification read-status migration.
