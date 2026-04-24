from app.database import get_connection, init_db

CUSTOMERS = [
    ("Alice Monroe",   "alice@example.com"),
    ("Ben Carter",     "ben@example.com"),
    ("Clara Diaz",     "clara@example.com"),
    ("David Kim",      "david@example.com"),
    ("Eva Rossi",      "eva@example.com"),
]

BOOKS = [
    ("The Midnight Library",      "Matt Haig",         "978-0525559474", 16.99, "Fiction"),
    ("Atomic Habits",             "James Clear",        "978-0735211292", 18.99, "Self-Help"),
    ("Dune",                      "Frank Herbert",      "978-0441013593", 14.99, "Science Fiction"),
    ("Educated",                  "Tara Westover",      "978-0399590504", 17.99, "Memoir"),
    ("The Name of the Wind",      "Patrick Rothfuss",   "978-0756404741", 15.99, "Fantasy"),
    ("Sapiens",                   "Yuval Noah Harari",  "978-0062316097", 19.99, "Non-Fiction"),
    ("Where the Crawdads Sing",   "Delia Owens",        "978-0735224292", 16.99, "Fiction"),
    ("Project Hail Mary",         "Andy Weir",          "978-0593135204", 18.99, "Science Fiction"),
]

# (customer_index, status, shipping_address, [(book_index, quantity)],
#  payment_method, payment_status, amount_books, amount_tax, amount_shipping)
ORDERS = [
    (0, "delivered", "12 Oak Street, Portland OR 97201",  [(0, 1), (1, 1)], "credit_card", "paid",   35.98, 2.88, 4.99),
    (0, "shipped",   "12 Oak Street, Portland OR 97201",  [(2, 1)],          "gift_card",   "paid",   14.99, 1.20, 4.99),
    (1, "delivered", "88 Maple Ave, Austin TX 78701",     [(3, 1), (4, 1)], "credit_card", "paid",   33.98, 2.72, 4.99),
    (1, "cancelled", "88 Maple Ave, Austin TX 78701",     [(5, 2)],          "gift_card",   "voided", 39.98, 3.20, 4.99),
    (2, "pending",   "5 River Rd, Chicago IL 60601",      [(6, 1)],          "credit_card", "paid",   16.99, 1.36, 4.99),
    (2, "delivered", "5 River Rd, Chicago IL 60601",      [(7, 1), (0, 1)], "credit_card", "paid",   35.98, 2.88, 4.99),
    (3, "pending",   "200 Pine Blvd, Seattle WA 98101",   [(1, 1)],          "gift_card",   "paid",   18.99, 1.52, 4.99),
    (3, "shipped",   "200 Pine Blvd, Seattle WA 98101",   [(2, 1), (3, 1)], "credit_card", "paid",   32.98, 2.64, 4.99),
    (4, "delivered", "9 Elm Court, Nashville TN 37201",   [(4, 2)],          "gift_card",   "paid",   31.98, 2.56, 4.99),
    (4, "pending",   "9 Elm Court, Nashville TN 37201",   [(5, 1), (6, 1), (7, 1)], "credit_card", "paid", 55.97, 4.48, 0.00),
]


def seed():
    init_db()
    with get_connection() as conn:
        if conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] > 0:
            print("Database already seeded — skipping.")
            return

        customer_ids = []
        for name, email in CUSTOMERS:
            cur = conn.execute("INSERT INTO customers (name, email) VALUES (?, ?)", (name, email))
            customer_ids.append(cur.lastrowid)

        book_ids = []
        for title, author, isbn, price, genre in BOOKS:
            cur = conn.execute(
                "INSERT INTO books (title, author, isbn, price, genre) VALUES (?, ?, ?, ?, ?)",
                (title, author, isbn, price, genre),
            )
            book_ids.append(cur.lastrowid)

        for cust_idx, status, address, items, pay_method, pay_status, amt_books, amt_tax, amt_ship in ORDERS:
            cur = conn.execute(
                "INSERT INTO orders (customer_id, status, shipping_address) VALUES (?, ?, ?)",
                (customer_ids[cust_idx], status, address),
            )
            order_id = cur.lastrowid

            for book_idx, qty in items:
                conn.execute(
                    "INSERT INTO order_items (order_id, book_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                    (order_id, book_ids[book_idx], qty, BOOKS[book_idx][3]),
                )

            conn.execute(
                """INSERT INTO payments (order_id, status, payment_method, amount_books, amount_tax, amount_shipping)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (order_id, pay_status, pay_method, amt_books, amt_tax, amt_ship),
            )

        print(f"Seeded {len(CUSTOMERS)} customers, {len(BOOKS)} books, {len(ORDERS)} orders with payments.")


if __name__ == "__main__":
    seed()
