"""API penghubung frontend HTML dengan PostgreSQL.

Endpoint:
  GET  /api/health
  GET  /api/categories
  GET  /api/products?category_id=&q=&limit=&offset=
  GET  /api/products/<id>
  POST /api/orders
  GET  /api/orders/<id>
"""
import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request

app = Flask(__name__)
app.json.ensure_ascii = False

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "ecommerce_db"),
    "user": os.getenv("DB_USER", "ecommerce_user"),
    "password": os.getenv("DB_PASSWORD", ""),
    "connect_timeout": 5,
}


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def connect():
    return psycopg2.connect(**DB_CONFIG)


@contextmanager
def db_cursor(commit=False):
    conn = connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def serialize(row):
    return {key: jsonable(value) for key, value in row.items()}


@app.errorhandler(ApiError)
def handle_api_error(err):
    return jsonify(error=err.message), err.status


@app.errorhandler(psycopg2.Error)
def handle_db_error(err):
    # Detail teknis hanya masuk log container, tidak dikirim ke browser.
    app.logger.exception("Kesalahan database")
    return jsonify(error="Gagal terhubung ke database"), 500


@app.get("/api/health")
def health():
    with db_cursor() as cur:
        cur.execute("SELECT 1 AS ok")
        cur.fetchone()
    return jsonify(status="ok")


@app.get("/api/categories")
def list_categories():
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.name, COUNT(p.id)::int AS product_count
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id
            GROUP BY c.id, c.name
            ORDER BY c.name
            """
        )
        rows = cur.fetchall()
    return jsonify([serialize(row) for row in rows])


@app.get("/api/products")
def list_products():
    category_id = request.args.get("category_id", type=int)
    keyword = (request.args.get("q") or "").strip()
    limit = min(max(request.args.get("limit", 60, type=int), 1), 100)
    offset = max(request.args.get("offset", 0, type=int), 0)

    params = {
        "category_id": category_id,
        "pattern": f"%{keyword}%",
        "limit": limit,
        "offset": offset,
    }
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.name, p.price, p.stock,
                   p.category_id, c.name AS category
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE (%(category_id)s::int IS NULL OR p.category_id = %(category_id)s)
              AND p.name ILIKE %(pattern)s
            ORDER BY p.id
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            params,
        )
        rows = cur.fetchall()
    return jsonify([serialize(row) for row in rows])


@app.get("/api/products/<int:product_id>")
def get_product(product_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.name, p.price, p.stock,
                   p.category_id, c.name AS category
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.id = %s
            """,
            (product_id,),
        )
        row = cur.fetchone()
    if not row:
        raise ApiError("Produk tidak ditemukan", 404)
    return jsonify(serialize(row))


@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Body harus berupa JSON")

    customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
    items = data.get("items") if isinstance(data.get("items"), list) else []

    full_name = str(customer.get("full_name") or "").strip()
    email = str(customer.get("email") or "").strip().lower()
    phone = str(customer.get("phone") or "").strip() or None
    city = str(customer.get("city") or "").strip() or None

    if not full_name:
        raise ApiError("Nama lengkap wajib diisi")
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ApiError("Email tidak valid")
    if not items:
        raise ApiError("Keranjang masih kosong")

    quantities = {}
    for item in items:
        if not isinstance(item, dict):
            raise ApiError("Format item tidak valid")
        try:
            product_id = int(item.get("product_id"))
            quantity = int(item.get("quantity"))
        except (TypeError, ValueError):
            raise ApiError("product_id dan quantity harus berupa angka")
        if product_id <= 0 or quantity <= 0:
            raise ApiError("product_id dan quantity harus lebih dari 0")
        quantities[product_id] = quantities.get(product_id, 0) + quantity

    with db_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM customers WHERE lower(email) = lower(%s)", (email,))
        existing = cur.fetchone()
        if existing:
            customer_id = existing["id"]
            cur.execute(
                """
                UPDATE customers
                SET full_name = %s,
                    phone = COALESCE(%s, phone),
                    city = COALESCE(%s, city)
                WHERE id = %s
                """,
                (full_name, phone, city, customer_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO customers (full_name, email, phone, city)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (full_name, email, phone, city),
            )
            customer_id = cur.fetchone()["id"]

        # Kunci baris produk supaya stok tidak balapan antar request.
        cur.execute(
            """
            SELECT id, name, price, stock
            FROM products
            WHERE id = ANY(%s)
            ORDER BY id
            FOR UPDATE
            """,
            (sorted(quantities),),
        )
        products = {row["id"]: row for row in cur.fetchall()}

        missing = [str(pid) for pid in quantities if pid not in products]
        if missing:
            raise ApiError("Produk tidak ditemukan: " + ", ".join(missing), 404)

        for pid, quantity in quantities.items():
            product = products[pid]
            if product["stock"] < quantity:
                raise ApiError(
                    f'Stok "{product["name"]}" tidak cukup '
                    f'(tersisa {product["stock"]})'
                )

        total = sum(
            products[pid]["price"] * quantity for pid, quantity in quantities.items()
        )

        cur.execute(
            """
            INSERT INTO orders (customer_id, status, total_amount)
            VALUES (%s, 'pending', %s)
            RETURNING id, order_date, status, total_amount
            """,
            (customer_id, total),
        )
        order = cur.fetchone()

        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO order_items (order_id, product_id, quantity, unit_price)
            VALUES %s
            """,
            [
                (order["id"], pid, quantity, products[pid]["price"])
                for pid, quantity in quantities.items()
            ],
        )

        for pid, quantity in quantities.items():
            cur.execute(
                "UPDATE products SET stock = stock - %s WHERE id = %s",
                (quantity, pid),
            )

    return (
        jsonify(
            order=serialize(order),
            customer={
                "id": customer_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "city": city,
            },
            items=[
                {
                    "product_id": pid,
                    "name": products[pid]["name"],
                    "quantity": quantity,
                    "unit_price": jsonable(products[pid]["price"]),
                    "subtotal": jsonable(products[pid]["price"] * quantity),
                }
                for pid, quantity in quantities.items()
            ],
        ),
        201,
    )


@app.get("/api/orders/<int:order_id>")
def get_order(order_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT o.id, o.status, o.order_date, o.total_amount,
                   c.full_name, c.email, c.phone, c.city
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            WHERE o.id = %s
            """,
            (order_id,),
        )
        order = cur.fetchone()
        if not order:
            raise ApiError("Pesanan tidak ditemukan", 404)

        cur.execute(
            """
            SELECT oi.product_id, p.name, oi.quantity, oi.unit_price,
                   (oi.quantity * oi.unit_price) AS subtotal
            FROM order_items oi
            JOIN products p ON p.id = oi.product_id
            WHERE oi.order_id = %s
            ORDER BY oi.id
            """,
            (order_id,),
        )
        items = cur.fetchall()

    return jsonify(order=serialize(order), items=[serialize(item) for item in items])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
