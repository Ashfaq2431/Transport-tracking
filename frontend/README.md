# TransitNotice frontend

The dashboard is a React/Vite app that presents official transit advisories,
server-side search/filtering and pagination, revision comparisons, source
monitoring, notifications, analytics, and CSV export. Route and area
watchlists plus notification read state are persisted in browser localStorage.
It uses plain CSS and does not require an icon or UI framework.

## Run locally

From this directory:

```powershell
npm install
npm run dev
```

Vite proxies `/api` requests to `http://localhost:8000`, so start the FastAPI
application separately (`python -m uvicorn backend.app.main:app --reload`).
The dashboard requests advisory, history, summary, source, refresh-run, and
alert data from the API. CSV export uses the active filters and fetches the
maximum API page size; source refresh actions call the source refresh endpoint.
If the API is unavailable it shows an error state and never substitutes
unverified or hardcoded transport notices.

Create a production bundle with `npm run build`.
