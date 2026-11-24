-- schema.sql : Skema basis data E-Commerce Lokal
DROP TABLE IF EXISTS order_items, orders, products, categories, customers CASCADE;

CREATE TABLE customers (
    id          SERIAL PRIMARY KEY,
    full_name   VARCHAR(100) NOT NULL,
    email       VARCHAR(120) NOT NULL UNIQUE,
    phone       VARCHAR(20),
    city        VARCHAR(60),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE categories (
    id    SERIAL PRIMARY KEY,
    name  VARCHAR(60) NOT NULL UNIQUE
);

CREATE TABLE products (
    id           SERIAL PRIMARY KEY,
    category_id  INT NOT NULL REFERENCES categories(id),
    name         VARCHAR(100) NOT NULL,
    price        NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    stock        INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    id            SERIAL PRIMARY KEY,
    customer_id   INT NOT NULL REFERENCES customers(id),
    order_date    TIMESTAMP NOT NULL DEFAULT NOW(),
    status        VARCHAR(20) NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','paid','shipped','completed','cancelled')),
    total_amount  NUMERIC(14,2) NOT NULL DEFAULT 0
);

CREATE TABLE order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id  INT NOT NULL REFERENCES products(id),
    quantity    INT NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(12,2) NOT NULL
);

-- ===== Data contoh =====
INSERT INTO customers (full_name, email, phone, city) VALUES
 ('Siti Rahmawati', 'siti.rahmawati@example.com', '0812-5550-0101', 'Pontianak'),
 ('Budi Santoso',   'budi.santoso@example.com',   '0813-5550-0102', 'Singkawang'),
 ('Andi Pratama',   'andi.pratama@example.com',   '0857-5550-0103', 'Pontianak'),
 ('Maya Lestari',   'maya.lestari@example.com',   '0821-5550-0104', 'Sambas');

INSERT INTO categories (name) VALUES
 ('Makanan dan Minuman'),
 ('Kerajinan dan Fashion'),
 ('Rumah Tangga');

INSERT INTO products (category_id, name, price, stock) VALUES
 (1, 'Kopi Sidikalang 250g',      45000, 120),
 (1, 'Keripik Pisang Pontianak',  25000, 200),
 (1, 'Lempok Durian 500g',        35000,  80),
 (2, 'Kain Tenun Sambas',        275000,  25),
 (2, 'Tas Anyaman Rotan',        150000,  40),
 (2, 'Kaos Khatulistiwa',         90000,  60),
 (3, 'Tikar Purun',               85000,  30),
 (3, 'Lampu Meja Rotan',         120000,  15);

INSERT INTO orders (customer_id, order_date, status) VALUES
 (1, NOW() - INTERVAL '5 days', 'paid'),
 (2, NOW() - INTERVAL '4 days', 'shipped'),
 (3, NOW() - INTERVAL '2 days', 'completed'),
 (1, NOW() - INTERVAL '1 day',  'pending');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
 (1, 1, 2,  45000), (1, 2, 3,  25000),
 (2, 4, 1, 275000), (2, 6, 2,  90000),
 (3, 5, 1, 150000),
 (4, 3, 4,  35000), (4, 7, 1,  85000);

UPDATE orders o
SET total_amount = s.total
FROM (SELECT order_id, SUM(quantity * unit_price) AS total
      FROM order_items GROUP BY order_id) s
WHERE o.id = s.order_id;
