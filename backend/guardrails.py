"""
guardrails.py — Domain restriction for the chat interface.
Only business dataset queries are allowed.
"""

import re

OUT_OF_SCOPE_RESPONSE = (
    "This system is designed to answer questions related to the provided "
    "Order-to-Cash dataset only. I can help with queries about sales orders, "
    "deliveries, invoices, payments, customers, products, and journal entries."
)

# Keywords that indicate a domain-relevant query
DOMAIN_KEYWORDS = [
    "order", "delivery", "deliveries", "invoice", "payment", "customer",
    "product", "billing", "bill", "shipment", "ship", "material", "plant",
    "journal", "entry", "entries", "gl", "account", "fiscal", "cash",
    "sales", "purchase", "vendor", "finance", "financial", "revenue",
    "amount", "currency", "quantity", "status", "document", "trace",
    "flow", "incomplete", "broken", "unbilled", "undelivered", "overdue",
    "highest", "lowest", "total", "count", "how many", "which", "list",
    "find", "show", "what", "when", "where", "who",
]

# Hard-blocked topics — reject even if they contain domain words
BLOCKED_PATTERNS = [
    r"\bwrite\s+(a\s+)?(poem|story|essay|song|code|function|script)\b",
    r"\bwhat\s+is\s+(the\s+)?(capital|population|president|prime minister)\b",
    r"\b(recipe|weather|news|sports|movie|music|celebrity)\b",
    r"\bignore\s+(previous|above|prior|all)\b",
    r"\bact\s+as\b",
    r"\bpretend\b",
    r"\bforget\s+your\s+instructions\b",
    r"\bsystem\s+prompt\b",
    r"\bjailbreak\b",
]


def is_domain_query(question: str) -> bool:
    """Return True if the question is about the business dataset."""
    q_lower = question.lower().strip()

    # Block prompt injection / jailbreak attempts
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, q_lower):
            return False

    # Very short / nonsensical queries — let LLM handle
    if len(q_lower) < 4:
        return False

    # Check for domain keywords
    return any(kw in q_lower for kw in DOMAIN_KEYWORDS)
