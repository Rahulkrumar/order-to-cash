import sqlite3, os

DB_PATH = os.environ.get("DB_PATH", "order_to_cash.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(sql: str) -> list:
    conn = get_db()
    try:
        cursor = conn.execute(sql)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        raise ValueError(f"SQL error: {e}")
    finally:
        conn.close()

def get_schema_info() -> str:
    conn = get_db()
    lines = []
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        for t in tables:
            cur = conn.execute(f"PRAGMA table_info({t})")
            cols = ", ".join(f"{c[1]}({c[2]})" for c in cur.fetchall())
            lines.append(f"TABLE {t}: {cols}")
    finally:
        conn.close()
    return "\n".join(lines)
