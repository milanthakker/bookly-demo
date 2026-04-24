import json
from pathlib import Path
from typing import Optional
from app.database import get_connection
from app import sessions

HELP_CENTER_PATH = Path(__file__).parent.parent / "data" / "help_center.txt"

TOOL_DEFINITIONS = [
    {
        "name": "get_help_center",
        "description": (
            "Retrieve the Bookly help center content, which covers policies on password reset, "
            "shipping, refunds, returns, gift cards, payment methods, damaged orders, account suspension, "
            "privacy, and support hours. Call this whenever a customer asks a general question about "
            "how Bookly works or what its policies are."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_customer_orders",
        "description": (
            "Look up all orders placed by a customer using their email address. "
            "Returns a summary of each order including order ID, status, date placed, and total value."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "The customer's email address.",
                }
            },
            "required": ["email"],
        },
    },
    {
        "name": "get_order_details",
        "description": (
            "Look up the details of a customer's order by order ID. "
            "Returns the order status, list of books, quantities, prices, and shipping address."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "The numeric order ID to look up.",
                }
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "get_order_payment",
        "description": (
            "Look up the payment details for a specific order by order ID. "
            "Returns the payment status, method (credit card or gift card), "
            "and a breakdown of amounts charged for books, tax, and shipping."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "The numeric order ID to look up payment details for.",
                }
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "process_refund",
        "description": (
            "Request a refund for a customer's order. Only orders with a status of 'pending' are eligible — "
            "orders that have been shipped, delivered, cancelled, or already refunded cannot be refunded. "
            "On success, updates the order status to 'refunded' and records the refund."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "The order ID to refund.",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional reason the customer provided for the refund.",
                },
            },
            "required": ["order_id"],
        },
    },
]


def get_help_center() -> str:
    return HELP_CENTER_PATH.read_text(encoding="utf-8")


def _order_owner_email(order_id: int) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT c.email FROM orders o JOIN customers c ON c.id = o.customer_id WHERE o.id = ?",
            (order_id,),
        ).fetchone()
    return row["email"] if row else None


def get_customer_orders(email: str, session_id: str) -> str:
    session = sessions.get_or_create(session_id)
    if session.customer_email and session.customer_email.lower() != email.lower():
        return json.dumps({"error": "You can only view orders for your own account."})

    with get_connection() as conn:
        customer = conn.execute(
            "SELECT id, name FROM customers WHERE email = ?", (email,)
        ).fetchone()

        if not customer:
            return json.dumps({"error": f"No customer found with email {email}."})

        orders = conn.execute(
            """
            SELECT o.id, o.status, o.created_at,
                   COUNT(oi.id) AS item_count,
                   SUM(oi.quantity * oi.unit_price) AS total
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            WHERE o.customer_id = ?
            GROUP BY o.id
            ORDER BY o.created_at DESC
            """,
            (customer["id"],),
        ).fetchall()

    return json.dumps({
        "customer_name": customer["name"],
        "customer_email": email,
        "orders": [
            {
                "order_id": row["id"],
                "status": row["status"],
                "placed_at": row["created_at"],
                "item_count": row["item_count"],
                "total": round(row["total"], 2),
            }
            for row in orders
        ],
    })


def get_order_details(order_id: int, session_id: str) -> str:
    session = sessions.get_or_create(session_id)
    if not session.customer_email:
        return json.dumps({"error": "Please identify yourself with your email address before looking up order details."})
    owner = _order_owner_email(order_id)
    if owner is None:
        return json.dumps({"error": f"No order found with ID {order_id}."})
    if owner.lower() != session.customer_email.lower():
        return json.dumps({"error": "You can only view your own orders."})

    with get_connection() as conn:
        order = conn.execute(
            """
            SELECT o.id, o.status, o.shipping_address, o.created_at, c.name, c.email
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()

        if not order:
            return json.dumps({"error": f"No order found with ID {order_id}."})

        items = conn.execute(
            """
            SELECT b.title, b.author, oi.quantity, oi.unit_price
            FROM order_items oi
            JOIN books b ON b.id = oi.book_id
            WHERE oi.order_id = ?
            """,
            (order_id,),
        ).fetchall()

    return json.dumps({
        "order_id": order["id"],
        "status": order["status"],
        "shipping_address": order["shipping_address"],
        "placed_at": order["created_at"],
        "customer_name": order["name"],
        "customer_email": order["email"],
        "items": [
            {
                "title": row["title"],
                "author": row["author"],
                "quantity": row["quantity"],
                "unit_price": row["unit_price"],
            }
            for row in items
        ],
    })


def get_order_payment(order_id: int, session_id: str) -> str:
    session = sessions.get_or_create(session_id)
    if not session.customer_email:
        return json.dumps({"error": "Please identify yourself with your email address before looking up payment details."})
    owner = _order_owner_email(order_id)
    if owner is None:
        return json.dumps({"error": f"No order found with ID {order_id}."})
    if owner.lower() != session.customer_email.lower():
        return json.dumps({"error": "You can only view payment details for your own orders."})

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT p.status, p.payment_method, p.amount_books, p.amount_tax,
                   p.amount_shipping, p.created_at
            FROM payments p
            WHERE p.order_id = ?
            """,
            (order_id,),
        ).fetchone()

        if not row:
            return json.dumps({"error": f"No payment record found for order {order_id}."})

    return json.dumps({
        "order_id": order_id,
        "payment_status": row["status"],
        "payment_method": row["payment_method"],
        "amount_books": row["amount_books"],
        "amount_tax": row["amount_tax"],
        "amount_shipping": row["amount_shipping"],
        "amount_total": round(row["amount_books"] + row["amount_tax"] + row["amount_shipping"], 2),
        "paid_at": row["created_at"],
    })


_INELIGIBLE_STATUSES = {"shipped", "delivered", "cancelled", "refunded"}


def process_refund(order_id: int, session_id: str, reason: Optional[str] = None) -> str:
    session = sessions.get_or_create(session_id)
    if not session.customer_email:
        return json.dumps({"error": "Please identify yourself with your email address before requesting a refund."})

    owner = _order_owner_email(order_id)
    if owner is None:
        return json.dumps({"error": f"No order found with ID {order_id}."})
    if owner.lower() != session.customer_email.lower():
        return json.dumps({"error": "You can only request refunds for your own orders."})

    with get_connection() as conn:
        order = conn.execute(
            "SELECT status FROM orders WHERE id = ?", (order_id,)
        ).fetchone()

        if order["status"] in _INELIGIBLE_STATUSES:
            return json.dumps({
                "error": f"Order {order_id} cannot be refunded because its status is '{order['status']}'."
            })

        conn.execute(
            "UPDATE orders SET status = 'refunded', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (order_id,),
        )
        payment = conn.execute(
            "SELECT amount_books, amount_tax, amount_shipping FROM payments WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        refund_amount = round(
            payment["amount_books"] + payment["amount_tax"] + payment["amount_shipping"], 2
        ) if payment else 0.0
        conn.execute(
            "UPDATE payments SET status = 'refunded' WHERE order_id = ?",
            (order_id,),
        )
        conn.execute(
            "INSERT INTO refunds (order_id, reason, amount) VALUES (?, ?, ?)",
            (order_id, reason, refund_amount),
        )

    return json.dumps({
        "success": True,
        "order_id": order_id,
        "refund_amount": refund_amount,
        "message": f"Order {order_id} has been successfully refunded for ${refund_amount:.2f}.",
    })


def execute_tool(name: str, inputs: dict, session_id: str) -> str:
    if name == "get_help_center":
        return get_help_center()
    if name == "get_customer_orders":
        return get_customer_orders(inputs["email"], session_id)
    if name == "get_order_details":
        return get_order_details(inputs["order_id"], session_id)
    if name == "get_order_payment":
        return get_order_payment(inputs["order_id"], session_id)
    if name == "process_refund":
        return process_refund(inputs["order_id"], session_id, inputs.get("reason"))
    return json.dumps({"error": f"Unknown tool: {name}"})
