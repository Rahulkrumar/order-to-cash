# AI Coding  Logs — Order to Cash Project

**Tool Used:** Claude.ai (Claude Sonnet 4.6)  
**Session Date:**  
**Project:** Graph-Based Data Modeling and Query System (Forward Deployed Engineer Assignment)

---

## Session Overview

This document captures the full AI-assisted development and deployment session for the Order to Cash graph query system. The session covered backend/frontend verification, deployment debugging, API key configuration, and model version fixes.

---

## Session Log

---

### Turn 1 — Project Understanding

**User Prompt:**
> Shared the Forward Deployed Engineer assignment PDF. Asked what needs to be done next after completing backend and frontend.

**Claude Response:**
Analyzed the assignment requirements and identified the submission checklist:
- Working demo link
- Public GitHub repository
- README explaining architecture
- AI coding session logs
- App fully tested

**Reasoning:** Read the assignment document carefully to understand evaluation criteria before giving guidance.

---

### Turn 2 — Code Review

**User Prompt:**
> Uploaded `order-to-cash-project.zip` and `sap-order-to-cash-dataset.zip`. Asked what's done and what's next.

**Claude Action:**
Extracted and analyzed the zip contents. Found:
- `backend/` — FastAPI + SQLite + NetworkX + Groq LLM
- `frontend/` — React 18 + D3 v7 + Vite + Tailwind
- `README.md` — Already comprehensive
- `render.yaml` — Render deployment config

**Key findings from code review:**
```
backend/
  main.py       — FastAPI app, CORS, startup ingestion
  ingest.py     — JSONL → SQLite (11 entity folders, 753 nodes)
  graph.py      — SQLite → NetworkX DiGraph → JSON API
  llm.py        — NL → SQL pipeline (Groq llama3-70b-8192)
  guardrails.py — Two-layer domain restriction
  database.py   — SQLite query executor
```

**Conclusion:** Backend and frontend were complete. Main gap was deployment connectivity and submission materials.

---

### Turn 3 — Backend URL Verification

**User Prompt:**
> Provided backend URL: `https://order-to-cash.onrender.com`

**Claude Action:**
Attempted to fetch `/health` endpoint. Confirmed backend was live returning:
```json
{"status": "ok", "message": "Order to Cash API running"}
```

**Next step identified:** Connect frontend `VITE_API_URL` to backend on Vercel.

---

### Turn 4 — Frontend-Backend Connection

**User Prompt:**
> Shared screenshot of Vercel redeploy success page.

**Claude Response:**
Instructed user to:
1. Set `VITE_API_URL=https://order-to-cash.onrender.com` in Vercel Environment Variables
2. Redeploy frontend

---

### Turn 5 — First Chat Test (401 Error)

**User Prompt:**
> Shared screenshot showing graph loaded (753 nodes, 551 edges) but chat returning:
> `LLM API error: Client error '401 Unauthorized' for url https://api.groq.com/openai/v1/chat/completions`

**Claude Diagnosis:**
`401 Unauthorized` = GROQ_API_KEY on Render is invalid or expired.

**Debugging steps suggested:**
1. Check Render Environment tab for `GROQ_API_KEY`
2. Verify key starts with `gsk_`
3. Generate new key from console.groq.com if needed

---

### Turn 6 — Wrong Variable Name Identified

**User Prompt:**
> Shared screenshot of Render Environment showing variable named `order-to-cash` instead of `GROQ_API_KEY`.

**Claude Diagnosis:**
Root cause found — variable name was `order-to-cash` but code reads `os.environ.get("GROQ_API_KEY", "")`. Wrong environment variable name.

**Fix:** Rename variable to `GROQ_API_KEY` and set correct Groq API key value.

---

### Turn 7 — 400 Bad Request (Model Deprecated)

**User Prompt:**
> After fixing variable name, error changed to:
> `LLM API error: Client error '400 Bad Request' for url https://api.groq.com/openai/v1/chat/completions`

**Claude Diagnosis:**
`400 Bad Request` with correct key = model name issue. Checked `llm.py` line 77:
```python
payload = {"model": "llama3-70b-8192", ...}
```

`llama3-70b-8192` was deprecated on Groq. Needed to update to current model.

**Fix applied:**
```python
# Before (deprecated):
"model": "llama3-70b-8192"

# After (working):
"model": "llama-3.3-70b-versatile"
```

**Prompt to user:** Edit `llm.py` on GitHub directly using pencil icon, commit change — Render will auto-redeploy.

---

### Turn 8 — Successful Deployment

**User Prompt:**
> Shared Render Events log showing:
> `Deploy live for deda22d: Merge branch 'main' — March 24, 2026 at 3:03 PM`

**Claude Response:**
Confirmed successful deployment. Auto-deploy triggered by GitHub commit.

---

### Turn 9 — App Fully Working

**User Prompt:**
> Confirmed chat is now working.

**Status:** All systems operational ✅

---

## Debugging Workflow Summary

| Step | Error | Root Cause | Fix |
|------|-------|------------|-----|
| 1 | 401 Unauthorized | GROQ_API_KEY missing/expired | Generate new key on console.groq.com |
| 2 | 401 Unauthorized | Variable named `order-to-cash` instead of `GROQ_API_KEY` | Rename env variable on Render |
| 3 | 400 Bad Request | Deprecated model `llama3-70b-8192` | Update to `llama-3.3-70b-versatile` in llm.py |
| 4 | ✅ Working | — | — |

---

## Prompt Quality Examples

### Debugging Prompt Pattern
When errors occurred, Claude consistently:
1. Read the exact error message
2. Identified the specific HTTP status code meaning
3. Traced to root cause in code/config
4. Provided exact fix with before/after code

### Code Review Prompt
```
Analyzed zip structure → identified tech stack → found all 30 files →
read key files (main.py, llm.py, guardrails.py) → summarized architecture
```

### Environment Variable Debug
```
401 → "key invalid" → check Render env → found wrong variable name →
rename to GROQ_API_KEY → still 400 → check model name in llm.py →
found deprecated model → update → deploy → working
```

---

## Architecture Decisions Validated

During the session, the following architecture decisions were confirmed as correct:

**SQLite over PostgreSQL:** Zero infrastructure, LLMs know SQL fluently, 11 tables fit comfortably.

**Groq over OpenAI:** Fastest free tier, generous limits, excellent SQL generation with llama models.

**NetworkX in-memory graph:** 753 nodes fits in RAM, zero infra, fast startup on Render free tier.

**Two-layer guardrails:** Keyword filter (zero LLM cost) + LLM-level instruction catches semantic bypasses.

**temperature=0.1 for SQL generation:** Near-deterministic output needed for SQL; zero risks degenerate loops.

---

## Final Status

| Component | Status | URL |
|-----------|--------|-----|
| Frontend | ✅ Live | https://order-to-cash-two.vercel.app |
| Backend | ✅ Live | https://order-to-cash.onrender.com |
| Graph | ✅ 753 nodes, 551 edges | /graph endpoint |
| Chat/LLM | ✅ Working | Groq llama-3.3-70b-versatile |
| GitHub | ✅ Public | https://github.com/Rahulkrumar/order-to-cash |

---

*Session conducted using Claude.ai on , 2026*
