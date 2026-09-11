import os
import sqlite3
from pathlib import Path

# An in-memory database keeps the demo stateless: nothing is written to disk, so
# it runs on a read-only serverless filesystem (Vercel) and every cold start
# begins from identical seed data. That reproducibility matters for Arize
# experiments -- runs cannot contaminate each other.
#
# Set BOOKLY_DB_PATH to use a file instead (handy for local inspection).
DB_PATH = os.getenv("BOOKLY_DB_PATH")

# Each caller opens its own connection, and a plain ":memory:" database would
# give every connection a separate empty DB. Shared-cache URI mode makes them
# all address the same one.
_MEMORY_URI = "file:bookly_demo?mode=memory&cache=shared"

# The shared in-memory DB lives only as long as at least one connection to it is
# open, so hold one for the process lifetime.
_keepalive: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    if DB_PATH:
        return sqlite3.connect(Path(DB_PATH))
    return sqlite3.connect(_MEMORY_URI, uri=True, check_same_thread=False)


# Serverless hosts do not guarantee that ASGI lifespan startup runs, so schema
# creation and seeding are driven from the first DB access instead of relying on
# it. ensure_ready() is idempotent and cheap after the first call.
_ready = False


def ensure_ready():
    global _ready
    if _ready:
        return
    _ready = True  # set first: init_db/seed call get_connection re-entrantly

    from app.seed import seed  # imported here to avoid a circular import

    init_db()
    seed()


def get_connection() -> sqlite3.Connection:
    global _keepalive
    if not DB_PATH and _keepalive is None:
        _keepalive = _connect()

    ensure_ready()

    conn = _connect()
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
