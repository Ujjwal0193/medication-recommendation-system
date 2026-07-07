# MediGuard — Product Website

Full multi-page React (Vite) site for MediGuard: landing page, live demo, about,
and docs. The live-demo page calls the FastAPI backend.

## Pages

| Route | Page |
|---|---|
| `/` | Landing — hero, headline metrics, feature grid, pipeline diagram |
| `/#/demo` | Live demo — free-text **or** structured form → safety-checked recommendations |
| `/#/about` | Scope, hard boundaries, why the hybrid architecture, limitations |
| `/#/docs` | Tech stack, evaluation metrics, data sources, browsable drug knowledge base |

Uses `HashRouter`, so the built site also works opened as static files.

## Run

Start the API first (from repo root):

```bash
uvicorn mediguard.api.app:app --port 8000
```

Then the site:

```bash
cd ui
npm install
npm run dev        # http://localhost:5173  (proxies /api -> :8000)
```

Build for production: `npm run build` → `ui/dist/`.

## API endpoints the site uses

`GET /health` · `GET /drugs` · `GET /conditions` · `GET /drug/{name}` ·
`POST /recommend` · `POST /recommend/fhir`

The Vite dev proxy forwards `/api/*` to the FastAPI server on port 8000
(`vite.config.js`).
