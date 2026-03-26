# Order to Cash — Graph-Based Data Modeling & Query System

A context graph system with an LLM-powered conversational query interface for the SAP Order-to-Cash (O2C) business process.

## Dataset

Real SAP O2C JSONL dataset with **753 graph nodes** and **551 edges** across:

| Entity | Rows | Table |
|--------|------|-------|
| Sales Order Headers | 100 | `sales_order_headers` |
| Sales Order Items | 167 | `sales_order_items` |
| Billing Documents | 80 | `billing_documents` |
| Outbound Deliveries | 86 | `outbound_delivery_headers` |
| Journal Entry Items | 123 | `journal_entry_items` |
| Payments (AR) | 120 | `payments` |
| Business Partners | 8 | `business_partners` |
| Product Descriptions | 69 | `product_descriptions` |
| Plants | 44 | `plants` |
| Customer Company Assignments | 8 | `customer_company_assignments` |
| Customer Sales Area Assignments | 28 | `customer_sales_area_assignments` |

---

## Architecture

```
frontend/          React 18 + D3 v7 + Vite + Tailwind
backend/
  main.py          FastAPI app + CORS
  ingest.py        JSONL → SQLite (all 11 entity folders)
  graph.py         SQLite → NetworkX DiGraph → JSON API
  llm.py           NL → SQL (Groq/Gemini) → natural language answer
  guardrails.py    Domain restriction (keyword + LLM-level)
  database.py      SQLite query executor + schema info
  data/            Place sap-o2c-data/ folder here
```

---

## Graph Model

### Nodes (9 types)

| Type | Source Table | Identifier |
|------|-------------|------------|
| Customer | `business_partners` | `customer` |
| SalesOrder | `sales_order_headers` | `salesOrder` |
| OrderItem | `sales_order_items` | `salesOrder/salesOrderItem` |
| Product | `product_descriptions` | `product` |
| Delivery | `outbound_delivery_headers` | `deliveryDocument` |
| BillingDocument | `billing_documents` | `billingDocument` |
| JournalEntry | `journal_entry_items` (grouped by `accountingDocument`) | `accountingDocument` |
| Payment | `payments` (grouped by `clearingAccountingDocument`) | `clearingAccountingDocument` |
| Plant | `plants` | `plant` |

### Edges (confirmed from real data)

```
Customer        --[PLACED]-------→ SalesOrder
SalesOrder      --[HAS_ITEM]-----→ OrderItem
OrderItem       --[IS_MATERIAL]--→ Product
OrderItem       --[PRODUCED_AT]--→ Plant
Customer        --[BILLED_TO]----→ BillingDocument
BillingDocument --[POSTS_TO]-----→ JournalEntry   (via accountingDocument)
BillingDocument --[SETTLED_BY]---→ Payment        (via accountingDocument)
Customer        --[PAID_BY]------→ Payment
```

> Note: The dataset has no direct FK from BillingDocument → SalesOrder. The link is through `soldToParty` (customer). This is modelled in the graph via the Customer hub node.

---

## LLM Prompting Strategy

### Pipeline

```
User question
    ↓
[Guardrail — keyword + injection filter]
    ↓
System prompt = schema + JOIN keys + status code glossary + business rules
User message  = question + last 6 history turns (conversation memory)
    ↓ Groq llama3-70b, temperature=0.1
JSON: { "sql": "SELECT ...", "explanation": "..." }
    ↓
SQLite execution
    ↓
Answer prompt = question + SQL + results (≤15 rows)
    ↓ Groq llama3-70b
Natural language answer + highlighted graph nodes
```

### Why temperature=0.1?
SQL generation needs near-determinism. Zero risks degenerate loops; 0.1 gives minimal variance while keeping output stable.

### Schema prompt design
The system prompt includes:
1. Full SQLite schema (all 11 tables, all column names + types)
2. Explicit JOIN keys (the dataset has no enforced FK constraints — the LLM needs to know which IDs connect which tables)
3. Status code glossary (`overallDeliveryStatus: A=Not delivered, B=Partial, C=Complete`)
4. Business rule translations ("delivered but not billed" → `overallDeliveryStatus='C' AND overallOrdReltdBillgStatus != 'C'`)
5. Strict JSON-only output format — no markdown, no prose outside the JSON

### Conversation memory
Last 6 message pairs are passed as history, enabling follow-ups like "and which of those are cancelled?" without re-stating context.

---

## Guardrails

Two-layer approach — **zero LLM cost for Layer 1 rejections**:

**Layer 1 — Python keyword + injection filter:**
- Requires at least one domain keyword (order, billing, payment, delivery, customer, plant, journal, material, etc.)
- Blocks prompt injection patterns: `ignore previous`, `act as`, `jailbreak`, `forget instructions`, `system prompt`
- Blocks clearly off-topic requests: poems, recipes, weather, movies, etc.

**Layer 2 — LLM instruction:**
- System prompt instructs the model: "If question is not about the O2C dataset, return `{"sql": null, "out_of_scope": true}`"
- Catches semantic bypasses that keyword matching misses

**Response:** `"This system is designed to answer questions related to the provided Order-to-Cash dataset only. I can help with queries about sales orders, deliveries, billing documents, payments, customers, products, and journal entries."`

---

## Example Queries (all validated on real data)

| Question | Key tables used |
|---|---|
| Which products are associated with the highest number of billing documents? | `sales_order_items` → `product_descriptions` → `billing_documents` |
| Trace the full flow of billing document 90504219 | `billing_documents` → `journal_entry_items` → `payments` |
| Find sales orders delivered but not billed | `sales_order_headers` WHERE `overallDeliveryStatus='C' AND overallOrdReltdBillgStatus != 'C'` |
| Which customer has the highest total billing value? | `billing_documents` GROUP BY `soldToParty` → `business_partners` |
| Show all cancelled billing documents | `billing_documents` WHERE `billingDocumentIsCancelled='true'` |
| Which plants have the most order items? | `sales_order_items` GROUP BY `productionPlant` → `plants` |
| List payments cleared in April 2025 | `payments` WHERE `clearingDate LIKE '2025-04%'` |
| Find orders with delivery blocks | `sales_order_headers` WHERE `deliveryBlockReason != ''` |

---

## Local Setup

### Backend

```bash
cd backend

pip install -r requirements.txt

# Place the dataset:
mkdir -p data
# Copy the sap-o2c-data/ folder into backend/data/
# so that backend/data/sap-o2c-data/sales_order_headers/ etc. exist

# Set LLM key (Groq recommended — fastest, generous free tier)
export GROQ_API_KEY=gsk_your_key_here
# OR
export GEMINI_API_KEY=your_key_here

uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install

# Point at the backend
echo "VITE_API_URL=http://localhost:8000" > .env.local

npm run dev
# → http://localhost:5173
```

---

## Deployment

### Backend → Render.com (free tier)

1. Push repo to GitHub
2. New Web Service → root dir: `backend/`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Environment variables:
   - `GROQ_API_KEY` = your key
   - `DB_PATH` = `/tmp/otc.db`
6. Add the `data/sap-o2c-data/` folder to the repo (it's JSONL, small enough)

### Frontend → Vercel

1. New project → root dir: `frontend/`
2. Framework preset: Vite
3. Environment variable: `VITE_API_URL=https://your-app.onrender.com`
4. Deploy

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Frontend | React 18 + D3 v7 | D3 force simulation matches the reference UI exactly |
| Build | Vite + Tailwind | Fast dev, small bundle |
| Backend | FastAPI (Python) | Async, auto docs, easy deployment |
| Graph | NetworkX (in-memory) | Zero infra, fast startup, 753 nodes fits in RAM comfortably |
| Database | SQLite | Zero infra, LLMs know SQL fluently, easy to deploy |
| LLM | Groq llama3-70b | Fastest free tier, excellent SQL generation |
| Fallback LLM | Gemini 1.5 Flash | Google free tier, reliable fallback |
| Deployment | Render + Vercel | Both have generous free tiers, no credit card required |
