"""
Tests for process_refund eligibility checks and tool/prompt guardrails.

The production issue was: the agent called process_refund without first
calling get_order_details, causing errors on non-pending orders.
"""
import json
import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Minimal in-memory DB fixture
# ---------------------------------------------------------------------------

def _build_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT NOT NULL UNIQUE,
            price REAL NOT NULL,
            genre TEXT NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','shipped','delivered','cancelled','refunded')),
            shipping_address TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            book_id INTEGER NOT NULL REFERENCES books(id),
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL
        );
        CREATE TABLE payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
            status TEXT NOT NULL DEFAULT 'paid'
                CHECK(status IN ('paid','refunded','voided')),
            payment_method TEXT NOT NULL
                CHECK(payment_method IN ('credit_card','gift_card')),
            amount_books REAL NOT NULL,
            amount_tax REAL NOT NULL,
            amount_shipping REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE refunds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
            reason TEXT,
            amount REAL NOT NULL,
            refunded_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO customers (id, name, email) VALUES (1, 'Test User', 'test@example.com');
        INSERT INTO books (id, title, author, isbn, price, genre)
            VALUES (1, 'Sample Book', 'Author A', '111', 10.0, 'Fiction');
        INSERT INTO orders (id, customer_id, status, shipping_address)
            VALUES (10, 1, 'pending', '1 Main St');
        INSERT INTO orders (id, customer_id, status, shipping_address)
            VALUES (11, 1, 'cancelled', '1 Main St');
        INSERT INTO orders (id, customer_id, status, shipping_address)
            VALUES (12, 1, 'shipped', '1 Main St');
        INSERT INTO orders (id, customer_id, status, shipping_address)
            VALUES (13, 1, 'delivered', '1 Main St');
        INSERT INTO orders (id, customer_id, status, shipping_address)
            VALUES (14, 1, 'refunded', '1 Main St');
        INSERT INTO order_items (order_id, book_id, quantity, unit_price)
            VALUES (10, 1, 1, 10.0);
        INSERT INTO order_items (order_id, book_id, quantity, unit_price)
            VALUES (11, 1, 1, 10.0);
        INSERT INTO order_items (order_id, book_id, quantity, unit_price)
            VALUES (12, 1, 1, 10.0);
        INSERT INTO order_items (order_id, book_id, quantity, unit_price)
            VALUES (13, 1, 1, 10.0);
        INSERT INTO order_items (order_id, book_id, quantity, unit_price)
            VALUES (14, 1, 1, 10.0);
        INSERT INTO payments (order_id, status, payment_method, amount_books, amount_tax, amount_shipping)
            VALUES (10, 'paid', 'credit_card', 10.0, 1.0, 2.0);
        INSERT INTO payments (order_id, status, payment_method, amount_books, amount_tax, amount_shipping)
            VALUES (11, 'paid', 'credit_card', 10.0, 1.0, 2.0);
        INSERT INTO payments (order_id, status, payment_method, amount_books, amount_tax, amount_shipping)
            VALUES (12, 'paid', 'credit_card', 10.0, 1.0, 2.0);
        INSERT INTO payments (order_id, status, payment_method, amount_books, amount_tax, amount_shipping)
            VALUES (13, 'paid', 'credit_card', 10.0, 1.0, 2.0);
        INSERT INTO payments (order_id, status, payment_method, amount_books, amount_tax, amount_shipping)
            VALUES (14, 'refunded', 'credit_card', 10.0, 1.0, 2.0);
    """)
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_DB = None

@contextmanager
def _test_connection():
    global _TEST_DB
    yield _TEST_DB


def _make_session(email="test@example.com"):
    from app import sessions
    sid = "test-session"
    sessions._store[sid] = sessions.Session(customer_email=email)
    return sid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestProcessRefundEligibility(unittest.TestCase):
    """process_refund must reject ineligible order statuses without DB mutation."""

    def setUp(self):
        global _TEST_DB
        _TEST_DB = _build_test_db()
        self._patcher = patch("app.tools.get_connection", _test_connection)
        self._patcher.start()
        from app import sessions
        sessions._store.clear()

    def tearDown(self):
        self._patcher.stop()
        global _TEST_DB
        _TEST_DB.close()
        _TEST_DB = None

    def test_refund_pending_order_succeeds(self):
        from app.tools import process_refund
        sid = _make_session()
        result = json.loads(process_refund(order_id=10, session_id=sid))
        self.assertTrue(result.get("success"))
        self.assertAlmostEqual(result["refund_amount"], 13.0)

    def test_refund_cancelled_order_rejected(self):
        """Reproduces the production failure: refunding a cancelled order."""
        from app.tools import process_refund
        sid = _make_session()
        result = json.loads(process_refund(order_id=11, session_id=sid))
        self.assertIn("error", result)
        self.assertIn("cancelled", result["error"])

    def test_refund_shipped_order_rejected(self):
        from app.tools import process_refund
        sid = _make_session()
        result = json.loads(process_refund(order_id=12, session_id=sid))
        self.assertIn("error", result)
        self.assertIn("shipped", result["error"])

    def test_refund_delivered_order_rejected(self):
        from app.tools import process_refund
        sid = _make_session()
        result = json.loads(process_refund(order_id=13, session_id=sid))
        self.assertIn("error", result)
        self.assertIn("delivered", result["error"])

    def test_refund_already_refunded_order_rejected(self):
        from app.tools import process_refund
        sid = _make_session()
        result = json.loads(process_refund(order_id=14, session_id=sid))
        self.assertIn("error", result)
        self.assertIn("refunded", result["error"])


class TestToolDescriptionGuardrail(unittest.TestCase):
    """The process_refund tool description must instruct the agent to check
    order details first — this is the primary guardrail preventing the
    production failure pattern (agent skipping the eligibility check)."""

    def test_process_refund_description_requires_get_order_details_first(self):
        from app.tools import TOOL_DEFINITIONS
        refund_tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "process_refund")
        desc = refund_tool["description"].lower()
        self.assertIn("get_order_details", desc,
                      "process_refund description must mention get_order_details")
        self.assertIn("first", desc,
                      "process_refund description must say to call get_order_details FIRST")

    def test_process_refund_description_mentions_ineligible_statuses(self):
        from app.tools import TOOL_DEFINITIONS
        refund_tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "process_refund")
        desc = refund_tool["description"].lower()
        for status in ("cancelled", "shipped", "delivered", "refunded"):
            self.assertIn(status, desc,
                          f"process_refund description must list '{status}' as ineligible")


class TestSystemPromptGuardrail(unittest.TestCase):
    """The system prompt must explicitly instruct the agent to verify order
    status before processing a refund."""

    def test_system_prompt_requires_order_details_before_refund(self):
        from app.agent import BASE_SYSTEM_PROMPT
        prompt = BASE_SYSTEM_PROMPT.lower()
        self.assertIn("get_order_details", prompt,
                      "System prompt must reference get_order_details for refund eligibility")
        self.assertIn("refund", prompt,
                      "System prompt must address refund workflow")
        self.assertIn("pending", prompt,
                      "System prompt must specify 'pending' as the eligible status")


if __name__ == "__main__":
    unittest.main()
