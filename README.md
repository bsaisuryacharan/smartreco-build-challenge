# SmartReco — Behavioral AI Recommendation Platform

> SmartReco Build Challenge 2026 submission.

A full-stack learning platform that watches user behavior and generates personalized, persuasive course recommendations using a **LangGraph agentic RAG pipeline**.

---

## Architecture

```
Browser (Jinja2 + tracker.js)
        │ POST /api/events/batch  (batched, sendBeacon)
        ▼
FastAPI Backend
  ├── Auth (JWT cookie)
  ├── Catalog routes  ──► SQLite (SQLAlchemy)
  ├── Admin CRUD      ──► SQLite + ChromaDB  (dual-write)
  ├── Events API      ──► UserEvent table → triggers recommendation agent
  └── Recommendations API ◄─── stored Recommendation rows
              │
              ▼ (background task, threshold-gated)
    LangGraph Agent
      analyze_behavior → retrieve_products → evaluate_quality
           ↑ (refine_query loop)              ↓
                                    generate_recommendation
                                     (Mesh API / gpt-4o-mini)
              │
              ▼
         ChromaDB  (persistent vector store, cosine similarity)
              │
    APScheduler ── daily_digest @ 09:00 ──► SMTP / console log
    LangSmith   ── traces every agent run
```

---

## Features

| Feature | Status |
|---|---|
| Email/password auth with JWT cookie | ✅ |
| Admin product CRUD | ✅ |
| Dual-write: SQLite + ChromaDB | ✅ |
| Behavioral event tracking (batched, non-blocking) | ✅ |
| LangGraph agent (5-node graph with quality loop) | ✅ ⭐ |
| Semantic RAG retrieval + category re-ranking | ✅ ⭐ |
| Personalized persuasive narrative (Mesh API) | ✅ |
| Recommendation trigger (5-event / 5-min gate) | ✅ |
| Live recommendation panel (30s polling) | ✅ |
| APScheduler daily email digest | ✅ ⭐ |
| LangSmith observability tracing | ✅ ⭐ |

---

## Quick Start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd smartreco-build-challenge
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set MESH_API_KEY (required), SECRET_KEY, and optionally LangSmith/SMTP keys
```

### 3. Seed the database

```bash
python seed_products.py
# Creates 20 AI/ML courses and two demo accounts:
#   admin@smartreco.ai / admin123
#   user@smartreco.ai  / user123
```

### 4. Run the app

```bash
uvicorn app.main:app --reload
# Open http://localhost:8000
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `MESH_API_KEY` | **Yes** | Mesh API key (rsk_…) — all LLM calls route through Mesh |
| `SECRET_KEY` | Yes | JWT signing secret (change in production) |
| `LANGCHAIN_TRACING_V2` | No | Set `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | No | LangSmith API key |
| `LANGCHAIN_PROJECT` | No | LangSmith project name (default: `smartreco`) |
| `SMTP_HOST` | No | SMTP server for daily digests (logs to console if empty) |
| `DIGEST_HOUR` | No | Hour (0-23) to send daily digests (default: `9`) |

---

## How Recommendations Work

1. **Track**: `tracker.js` batches events (product views, searches, clicks, time spent) and POSTs them every 10s or every 5 events via `sendBeacon`.
2. **Trigger**: After each batch, a background task checks: ≥5 new events AND >5 min since last recommendation (or ≥3 events total with no recommendation yet).
3. **Agent**: LangGraph runs a 5-node graph:
   - `analyze_behavior` — extracts category/search/title signals from the last 20 events
   - `retrieve_products` — queries ChromaDB with cosine similarity
   - `evaluate_quality` — checks if ≥3 results have distance < 0.6
   - `refine_query` — if quality is poor, asks the LLM to broaden the query (max 2 retries)
   - `generate_recommendation` — re-ranks results by category interest weight, then calls Mesh API to write a personalized narrative
4. **Display**: The recommendation panel polls `GET /api/recommendations` every 30s and updates without page reload.

---

## Daily Digest

APScheduler fires at `DIGEST_HOUR:00` daily. For each user who was active in the last 24h, it fetches (or generates) their latest recommendation and sends it by email. If `SMTP_HOST` is not set, the digest is logged to the console instead.

---

## Project Structure

```
app/
  config.py          — pydantic-settings (reads .env)
  database.py        — SQLAlchemy engine + init_db()
  models.py          — User, Product, UserEvent, Recommendation
  auth.py            — JWT + bcrypt helpers
  dependencies.py    — FastAPI deps (get_db, get_current_user, require_admin)
  main.py            — App factory + lifespan
  routers/
    auth.py          — /login /register /logout
    admin.py         — /admin/products CRUD
    catalog.py       — / /product/{id} /search
    events.py        — POST /api/events/batch
    recommendations.py — GET/POST /api/recommendations
  services/
    vector_store.py  — ChromaDB singleton (upsert/delete/search)
    agent.py         — LangGraph recommendation graph
    scheduler.py     — APScheduler daily digest
static/
  js/tracker.js      — Batched event tracker + panel polling
  css/styles.css     — Dark theme design system
seed_products.py     — 20 AI/ML courses + demo users
```
