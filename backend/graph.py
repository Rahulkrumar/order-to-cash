"""
graph.py — Build NetworkX graph from SQLite using the real SAP O2C schema.

Nodes:
  Customer (business_partners)
  SalesOrder (sales_order_headers)
  OrderItem (sales_order_items)
  Product (product_descriptions)
  Delivery (outbound_delivery_headers)
  BillingDocument (billing_documents)
  JournalEntry (journal_entry_items - aggregated by accountingDocument)
  Payment (payments - aggregated by clearingAccountingDocument)
  Plant (plants)

Edges (confirmed from data):
  Customer → SalesOrder           (PLACED)
  SalesOrder → OrderItem          (HAS_ITEM)
  OrderItem → Product             (IS_MATERIAL)
  OrderItem → Plant               (PRODUCED_AT)
  Customer → BillingDocument      (BILLED_TO)
  BillingDocument → JournalEntry  (POSTS_TO)   via accountingDocument
  BillingDocument → Payment       (SETTLED_BY) via accountingDocument
  Customer → Payment              (PAID_BY)
"""

import sqlite3
import networkx as nx
from database import DB_PATH, get_db

G = nx.DiGraph()

NODE_COLORS = {
    "Customer":         "#60a5fa",
    "SalesOrder":       "#a78bfa",
    "OrderItem":        "#c4b5fd",
    "Product":          "#34d399",
    "Delivery":         "#38bdf8",
    "BillingDocument":  "#fbbf24",
    "JournalEntry":     "#f87171",
    "Payment":          "#fb923c",
    "Plant":            "#94a3b8",
}

NODE_SIZES = {
    "Customer": 14, "SalesOrder": 12, "BillingDocument": 12,
    "JournalEntry": 10, "Payment": 10, "OrderItem": 8,
    "Product": 10, "Delivery": 10, "Plant": 8,
}


def build_graph():
    global G
    G = nx.DiGraph()
    conn = get_db()
    try:
        _add_customers(conn)
        _add_sales_orders(conn)
        _add_order_items(conn)
        _add_products(conn)
        _add_deliveries(conn)
        _add_billing_documents(conn)
        _add_journal_entries(conn)
        _add_payments(conn)
        _add_plants(conn)
    finally:
        conn.close()
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def _node(nid, ntype, label, **data):
    G.add_node(nid, type=ntype, label=label,
               color=NODE_COLORS.get(ntype, "#94a3b8"),
               size=NODE_SIZES.get(ntype, 8), **data)


def _edge(src, dst, relation):
    if G.has_node(src) and G.has_node(dst):
        G.add_edge(src, dst, relation=relation)


def _add_customers(conn):
    for r in conn.execute("SELECT * FROM business_partners").fetchall():
        r = dict(r)
        nid = f"C-{r['customer']}"
        _node(nid, "Customer",
              r.get("businessPartnerFullName") or r.get("businessPartnerName") or r["customer"],
              **r)


def _add_sales_orders(conn):
    for r in conn.execute("SELECT * FROM sales_order_headers").fetchall():
        r = dict(r)
        nid = f"SO-{r['salesOrder']}"
        _node(nid, "SalesOrder", r["salesOrder"], **r)
        _edge(f"C-{r['soldToParty']}", nid, "PLACED")


def _add_order_items(conn):
    for r in conn.execute("SELECT * FROM sales_order_items").fetchall():
        r = dict(r)
        nid = f"OI-{r['salesOrder']}-{r['salesOrderItem']}"
        _node(nid, "OrderItem", f"{r['salesOrder']}/{r['salesOrderItem']}", **r)
        _edge(f"SO-{r['salesOrder']}", nid, "HAS_ITEM")
        if r.get("material"):
            _edge(nid, f"P-{r['material']}", "IS_MATERIAL")
        if r.get("productionPlant"):
            _edge(nid, f"PLT-{r['productionPlant']}", "PRODUCED_AT")


def _add_products(conn):
    seen = set()
    for r in conn.execute(
        "SELECT * FROM product_descriptions WHERE language='EN' OR language='' ORDER BY product"
    ).fetchall():
        r = dict(r)
        pid = r["product"]
        if pid in seen:
            continue
        seen.add(pid)
        nid = f"P-{pid}"
        _node(nid, "Product", r.get("productDescription", pid)[:40], **r)


def _add_deliveries(conn):
    for r in conn.execute("SELECT * FROM outbound_delivery_headers").fetchall():
        r = dict(r)
        nid = f"DEL-{r['deliveryDocument']}"
        _node(nid, "Delivery", r["deliveryDocument"], **r)


def _add_billing_documents(conn):
    for r in conn.execute("SELECT * FROM billing_documents").fetchall():
        r = dict(r)
        nid = f"BD-{r['billingDocument']}"
        _node(nid, "BillingDocument", r["billingDocument"], **r)
        _edge(f"C-{r['soldToParty']}", nid, "BILLED_TO")


def _add_journal_entries(conn):
    # Aggregate by accountingDocument (one node per accounting doc)
    seen = set()
    for r in conn.execute(
        "SELECT accountingDocument, companyCode, fiscalYear, glAccount, "
        "referenceDocument, postingDate, accountingDocumentType, customer, "
        "MIN(amountInTransactionCurrency) as amountInTransactionCurrency, "
        "transactionCurrency, COUNT(*) as lineItems "
        "FROM journal_entry_items GROUP BY accountingDocument"
    ).fetchall():
        r = dict(r)
        acct_doc = r["accountingDocument"]
        if acct_doc in seen:
            continue
        seen.add(acct_doc)
        nid = f"JE-{acct_doc}"
        _node(nid, "JournalEntry", acct_doc, **r)
        # Link: billing → journal via accountingDocument
        for bd in G.nodes:
            if G.nodes[bd].get("type") == "BillingDocument":
                if G.nodes[bd].get("accountingDocument") == acct_doc:
                    _edge(f"BD-{G.nodes[bd]['billingDocument']}", nid, "POSTS_TO")
                    break


def _add_payments(conn):
    # Aggregate by clearingAccountingDocument
    seen = set()
    for r in conn.execute(
        "SELECT clearingAccountingDocument, companyCode, fiscalYear, "
        "MIN(clearingDate) as clearingDate, customer, "
        "SUM(CAST(amountInTransactionCurrency AS REAL)) as totalAmount, "
        "transactionCurrency, glAccount, COUNT(*) as lineItems "
        "FROM payments WHERE clearingAccountingDocument IS NOT NULL AND clearingAccountingDocument != '' "
        "GROUP BY clearingAccountingDocument"
    ).fetchall():
        r = dict(r)
        clear_doc = r["clearingAccountingDocument"]
        if clear_doc in seen:
            continue
        seen.add(clear_doc)
        nid = f"PAY-{clear_doc}"
        _node(nid, "Payment", clear_doc, **r)
        # Link customer → payment
        if r.get("customer"):
            _edge(f"C-{r['customer']}", nid, "PAID_BY")
        # Link billing → payment via accountingDocument matching payments.accountingDocument
        for row2 in get_db().execute(
            "SELECT DISTINCT accountingDocument FROM payments WHERE clearingAccountingDocument=?",
            (clear_doc,)
        ).fetchall():
            acct = dict(row2)["accountingDocument"]
            # Find billing doc with that accountingDocument
            for bd_id, bd_data in [(n, G.nodes[n]) for n in G.nodes
                                   if G.nodes[n].get("type") == "BillingDocument"]:
                if bd_data.get("accountingDocument") == acct:
                    _edge(bd_id, nid, "SETTLED_BY")


def _add_plants(conn):
    for r in conn.execute("SELECT * FROM plants").fetchall():
        r = dict(r)
        nid = f"PLT-{r['plant']}"
        _node(nid, "Plant", r.get("plantName", r["plant"])[:30], **r)


def get_graph_data() -> dict:
    nodes = []
    for nid, data in G.nodes(data=True):
        ntype = data.get("type", "Unknown")
        nodes.append({
            "id": nid,
            "type": ntype,
            "label": data.get("label", nid),
            "color": data.get("color", NODE_COLORS.get(ntype, "#94a3b8")),
            "size": data.get("size", 8),
            "data": {k: v for k, v in data.items()
                     if k not in ("type", "label", "color", "size")},
        })
    edges = [
        {"source": s, "target": t, "relation": d.get("relation", "")}
        for s, t, d in G.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


def get_node_neighbors(node_id: str) -> dict:
    if node_id not in G:
        return {"error": f"Node {node_id} not found"}
    data = dict(G.nodes[node_id])
    neighbors = []
    for n in list(G.predecessors(node_id)) + list(G.successors(node_id)):
        rel = (G.edges[node_id, n].get("relation", "") if G.has_edge(node_id, n)
               else G.edges[n, node_id].get("relation", ""))
        neighbors.append({
            "id": n, "type": G.nodes[n].get("type", ""),
            "label": G.nodes[n].get("label", n), "relation": rel,
        })
    return {
        "id": node_id, "type": data.get("type", ""),
        "label": data.get("label", node_id),
        "data": {k: v for k, v in data.items() if k not in ("type", "label", "color", "size")},
        "neighbors": neighbors, "connections": len(neighbors),
    }


def find_nodes_by_value(value: str) -> list:
    value_lower = value.lower()
    matches = []
    for nid, data in G.nodes(data=True):
        if value_lower in str(data.get("label", "")).lower():
            matches.append(nid); continue
        for v in data.values():
            if value_lower in str(v).lower():
                matches.append(nid); break
    return matches
