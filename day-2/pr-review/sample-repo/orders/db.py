"""SQLite access. Every query uses parameters (standard 4)."""
import sqlite3

from orders import config


def connect(path: str = None) -> sqlite3.Connection:
    return sqlite3.connect(path or config.DB_PATH)


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, customer_id INTEGER, gross TEXT)")
    conn.commit()


def save_order(conn: sqlite3.Connection, order_id: str, customer_id: int, gross: str) -> None:
    conn.execute("INSERT INTO orders (id, customer_id, gross) VALUES (?, ?, ?)", (order_id, customer_id, gross))
    conn.commit()


def get_order(conn: sqlite3.Connection, order_id: str):
    return conn.execute("SELECT id, customer_id, gross FROM orders WHERE id = ?", (order_id,)).fetchone()


def get_orders_for_customer(conn: sqlite3.Connection, customer_id: int) -> list:
    return conn.execute("SELECT id, gross FROM orders WHERE customer_id = ?", (customer_id,)).fetchall()
