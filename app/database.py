import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "bookly.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                email       TEXT    NOT NULL UNIQUE,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS books (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                title   TEXT    NOT NULL,
                author  TEXT    NOT NULL,
                isbn    TEXT    NOT NULL UNIQUE,
                price   REAL    NOT NULL,
                genre   TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id      INTEGER NOT NULL REFERENCES customers(id),
                status           TEXT    NOT NULL DEFAULT 'pending'
                                         CHECK(status IN ('pending','shipped','delivered','cancelled','refunded')),
                shipping_address TEXT    NOT NULL,
                created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id   INTEGER NOT NULL REFERENCES orders(id),
                book_id    INTEGER NOT NULL REFERENCES books(id),
                quantity   INTEGER NOT NULL DEFAULT 1,
                unit_price REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS refunds (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id    INTEGER NOT NULL UNIQUE REFERENCES orders(id),
                reason      TEXT,
                amount      REAL    NOT NULL,
                refunded_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id        INTEGER NOT NULL UNIQUE REFERENCES orders(id),
                status          TEXT    NOT NULL DEFAULT 'paid'
                                        CHECK(status IN ('paid','refunded','voided')),
                payment_method  TEXT    NOT NULL
                                        CHECK(payment_method IN ('credit_card','gift_card')),
                amount_books    REAL    NOT NULL,
                amount_tax      REAL    NOT NULL,
                amount_shipping REAL    NOT NULL,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
