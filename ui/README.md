# MediGuard UI

React (Vite) dashboard for MediGuard. Enter a free-text patient report, get
ranked, safety-checked, explained medication recommendations with a mandatory
consent gate.

## Run

Start the API first (from repo root):

```bash
uvicorn mediguard.api.app:app --port 8000
```

Then the UI:

```bash
cd ui
npm install
npm run dev        # http://localhost:5173  (proxies /api -> :8000)
```

Build for production: `npm run build` → `ui/dist/`.

The UI calls `POST /api/recommend`; the Vite dev proxy forwards `/api/*` to the
FastAPI server on port 8000 (see `vite.config.js`).
