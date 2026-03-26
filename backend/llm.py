"""
llm.py — NL → SQL → answer pipeline using real SAP O2C schema.

Primary:  Groq (llama3-70b-8192) — fastest free tier
Fallback: Google Gemini 1.5 Flash
"""

import os, re, json, httpx
from database import execute_query
from graph import find_nodes_by_value

GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# Domain context injected into every SQL generation call
DOMAIN_CONTEXT = """
IMPORTANT JOIN KEYS (use these to link tables):
- sales_order_headers.customer     -> business_partners.customer
- sales_order_items.salesOrder      -> sales_order_headers.salesOrder
- sales_order_items.material       -> product_descriptions.product
- billing_documents.customer        -> business_partners.customer
- billing_documents.billingDocument -> journal_entry_items.accountingDocument
- payments.customer                 -> business_partners.customer
- sales_order_items.productionPlant -> plants.plant

STATUS CODES (for filtering broken/incomplete flows):
- overallDeliveryStatus: 'A'=Not delivered, 'B'=Partially, 'C'=Fully delivered
- overallOrdReltdBillgStatus: 'A'=Not billed, 'B'=Partially, 'C'=Fully billed
- billingDocumentIsCancelled: 'true'/'false'
- overallGoodsMovementStatus: 'A'=Not started, 'B'=Partial, 'C'=Complete

BUSINESS RULES:
- "Broken/incomplete flow" = sales orders where delivery not complete OR billing not complete
- overallDeliveryStatus != 'C' OR overallOrdReltdBillgStatus != 'C'
- "Delivered but not billed" = overallDeliveryStatus='C' AND overallOrdReltdBillgStatus != 'C'

# --- CRITICAL FIX FOR SOLD-TO-PARTY ERROR ---
- COLUMN MAPPING: In the 'billing_documents' table, the column name is 'customer'.
- NEVER use 'soldToParty' in SQL. If the user asks for 'sold to party', use 'billing_documents.customer'.
- 'T3.soldToParty' is an invalid column. Always use 'T3.customer' if T3 is billing_documents.
# --------------------------------------------

- Tracing a billing document: JOIN billing_documents -> journal_entry_items on accountingDocument
- Payments are linked to billing via payments.accountingDocument = billing_documents.accountingDocument
- All monetary amounts are stored as TEXT, use CAST(x AS REAL) for arithmetic
"""
"""

SYSTEM_PROMPT = """You are a SQL expert for an SAP Order-to-Cash (O2C) business data system.
Only answer questions about this dataset. Respond with OUT_OF_SCOPE for anything else.

SCHEMA:
{schema}

{domain_context}

Return ONLY valid JSON (no markdown, no explanation outside JSON):
{{"sql": "SELECT ...", "explanation": "one line"}}

Rules:
- SQLite only, SELECT statements only
- Use double quotes for string literals in WHERE clauses
- Always filter product_descriptions with language='EN' when joining
- For aggregations, always include GROUP BY
- NEVER use DROP/DELETE/INSERT/UPDATE/CREATE/ALTER
- Use only exact column names from the schema. Do not assume names like soldToParty.  # <--- YEH NAYI LINE ADD KAREIN
- If question is not about the O2C dataset, return: {"sql": null, "out_of_scope": true}
"""

ANSWER_PROMPT = """You are a business analyst. Answer this question based ONLY on the SQL results below.
Be specific with numbers, names, and document IDs. Under 120 words.

Question: {question}
SQL: {sql}
Results ({count} rows): {results}

If results are empty, say "No matching records found in the dataset."
"""


async def _call_groq(messages: list) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama3-70b-8192", "messages": messages, "temperature": 0.1, "max_tokens": 1024}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(GROQ_URL, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _call_gemini(prompt: str) -> str:
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _llm(messages: list, fallback_prompt: str) -> str:
    if GROQ_API_KEY:
        return await _call_groq(messages)
    if GEMINI_API_KEY:
        return await _call_gemini(fallback_prompt)
    raise RuntimeError("No LLM API key set. Add GROQ_API_KEY or GEMINI_API_KEY to environment.")


def _parse_sql_response(raw: str) -> dict:
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        return json.loads(clean)
    except Exception:
        m = re.search(r"SELECT\s+.+?(?:;|$)", raw, re.IGNORECASE | re.DOTALL)
        if m:
            return {"sql": m.group(0).strip(), "explanation": ""}
        return {"sql": None, "explanation": f"Could not parse: {raw[:300]}"}


async def generate_sql(question: str, schema: str, history: list) -> dict:
    system = SYSTEM_PROMPT.format(schema=schema, domain_context=DOMAIN_CONTEXT)
    messages = [{"role": "system", "content": system}]
    for h in history[-6:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": question})
    try:
        raw = await _llm(messages, f"{system}\n\nUser: {question}")
    except RuntimeError as e:
        return {"sql": None, "explanation": str(e)}
    except Exception as e:
        return {"sql": None, "explanation": f"LLM API error: {e}"}

    result = _parse_sql_response(raw)
    if result.get("out_of_scope") or "OUT_OF_SCOPE" in raw:
        result["out_of_scope"] = True
    return result


async def generate_answer(question: str, sql: str, results: list) -> str:
    prompt = ANSWER_PROMPT.format(
        question=question, sql=sql,
        count=len(results), results=json.dumps(results[:15], indent=2)
    )
    messages = [{"role": "user", "content": prompt}]
    try:
        return await _llm(messages, prompt)
    except Exception as e:
        if results:
            return f"Query returned {len(results)} result(s). Sample: {json.dumps(results[0])}"
        return "No results found."


def extract_highlighted_nodes(question: str, results: list) -> list:
    highlighted = set()
    for row in results[:15]:
        for val in row.values():
            if val and len(str(val)) > 3:
                highlighted.update(find_nodes_by_value(str(val)))
    for word in re.findall(r'\b\d{6,}\b', question):
        highlighted.update(find_nodes_by_value(word))
    return list(highlighted)[:25]


async def query_llm(question: str, schema: str, history: list) -> dict:
    sql_result = await generate_sql(question, schema, history)

    if sql_result.get("out_of_scope"):
        from guardrails import OUT_OF_SCOPE_RESPONSE
        return {"answer": OUT_OF_SCOPE_RESPONSE, "sql": None, "data": None, "highlighted_nodes": []}

    sql = sql_result.get("sql")
    if not sql:
        return {"answer": sql_result.get("explanation", "Could not generate a query for this question."),
                "sql": None, "data": None, "highlighted_nodes": []}

    try:
        results = execute_query(sql)
    except ValueError as e:
        return {"answer": f"Query error: {e}", "sql": sql, "data": None, "highlighted_nodes": []}

    answer = await generate_answer(question, sql, results)
    highlighted = extract_highlighted_nodes(question, results)

    return {"answer": answer, "sql": sql, "data": results[:50], "highlighted_nodes": highlighted}
