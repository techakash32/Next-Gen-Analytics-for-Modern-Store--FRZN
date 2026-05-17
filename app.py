from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import json
import os
from datetime import datetime, timedelta
import random
import math
from collections import defaultdict

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = 'frzn_secret_key_2026'
DB_PATH = 'database/frzn.db'

# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs('database', exist_ok=True)
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            slug TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category_id INTEGER,
            price REAL NOT NULL,
            original_price REAL,
            description TEXT,
            type TEXT,
            image_url TEXT,
            stock INTEGER DEFAULT 50,
            sizes TEXT DEFAULT '["XS","S","M","L","XL","XXL"]',
            badge TEXT,
            sku TEXT,
            is_featured INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            address TEXT,
            city TEXT,
            country TEXT DEFAULT 'US',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            payment_method TEXT DEFAULT 'card',
            shipping_address TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            size TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            product_id INTEGER,
            quantity INTEGER DEFAULT 1,
            size TEXT,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
    ''')
    conn.commit()
    conn.close()

def seed_data():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] > 0:
        conn.close()
        return

    # Categories
    categories = [
        ('Puffers', 'Heavy weight puffer jackets', 'puffers'),
        ('Shells',  'Technical shell outerwear',   'shells'),
    ]
    c.executemany("INSERT INTO categories (name, description, slug) VALUES (?,?,?)", categories)

    # Products — slugs must match the JS products object in index.html
    products = [
        ('aurora',      'AURORA SILVER',      1,  899.99, 1199.99, 'Reflective silver puffer with advanced thermal lining. Engineered for sub-zero performance.',      'REFLECTIVE PUFFER JACKET',   '/static/images/aurora-silver.png',     35, '["XS","S","M","L","XL","XXL"]', 'FEATURED',    'JCKT_001',           1),
        ('jckt001',     'JCKT_001 TOP LAYER', 1,  749.99,  999.99, 'Lightweight outer shell with wind-resistant coating. The foundation of the Cold Ops system.',    'LIGHTWEIGHT OUTER SHELL',    '/static/images/jckt001-top-layer.png', 40, '["XS","S","M","L","XL"]',     'NEW DROP',    'JCKT_001_TOP',       0),
        ('ghost',       'GHOST SILVER',       1, 1299.99, 1699.99, 'High-gloss silver puffer. Maximum visual impact, maximum insulation. For the few who lead.',       'HIGH-GLOSS PUFFER',          '/static/images/ghost-silver.png',      20, '["XS","S","M","L","XL"]',     'FLAGSHIP',    'JCKT_002_HEAVY',     1),
        ('stealth',     'STEALTH BLACK',      1, 1199.99, 1499.99, 'Matte black shield puffer with reinforced exterior panels. Built to withstand altitude exposure.',  'HEAVY SHIELD PUFFER',        '/static/images/stealth-black.png',     28, '["XS","S","M","L","XL","XXL"]', 'BEST SELLER', 'JCKT_003_SHIELD',    1),
        ('glacier',     'GLACIER WHITE',      1, 1299.99, 1799.99, 'Limited run white insulated puffer. Clean. Cold. Calculated. Only 20 units produced.',            'INSULATED PUFFER JACKET',    '/static/images/glacier-limited.png',   12, '["XS","S","M","L"]',          'LIMITED',     'JCKT_004_INSULATED', 1),
        ('navy',        'STEALTH NAVY',       1, 1129.00, 1399.00, 'Heavy puffer in deep navy. Oversized silhouette with interior storm baffles.',                    'HEAVY PUFFER JACKET',        '/static/images/stealth-navy.png',      32, '["XS","S","M","L","XL","XXL"]', None,          'JCKT_006_HEAVY',     0),
        ('gloss',       'POLAR GLOSS',        2,  999.99, 1299.99, 'Blue gloss shell puffer. Technical outer layer with sealed seams and articulated fit.',            'BLUE PUFFER JACKET',         '/static/images/polar-gloss.png',       25, '["XS","S","M","L","XL"]',     'NEW',         'JCKT_005_GLOSS',     0),
        ('icefield',    'ICEFIELD BLUE',      2,  999.99, 1299.99, 'Technical performance puffer with integrated heat channels. 4-way stretch face fabric.',          'TECH PUFFER JACKET',         '/static/images/icefield-blue.png',     30, '["XS","S","M","L","XL"]',     'TECH',        'JCKT_007_TECH',      0),
        ('polarwhite',  'POLAR WHITE',        2, 1499.99, 1899.99, 'Premium shell puffer. The pinnacle of the FRZN line. Weatherproof, windproof, unmatched.',        'SHELL PUFFER JACKET',        '/static/images/polar-white.png',       15, '["XS","S","M","L","XL"]',     'SHELL',       'JCKT_008_SHELL',     1),
    ]
    c.executemany('''INSERT INTO products
        (slug, name, category_id, price, original_price, description, type, image_url, stock, sizes, badge, sku, is_featured)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', products)

    # Customers
    customers = [
        ('Kai Blackwood', 'kai@frzn.io',      '+1-212-555-0101', '487 Pier Ave',        'Brooklyn'),
        ('Mara Cole',     'mara@gmail.com',   '+1-310-555-0102', '9 Sunset Blvd',       'Los Angeles'),
        ('Erik Voss',     'erik@gmail.com',   '+1-646-555-0103', '15 Franklin St',      'New York'),
        ('Sasha Lin',     'sasha@gmail.com',  '+1-415-555-0104', '230 Market St',       'San Francisco'),
        ('Dante Reyes',   'dante@gmail.com',  '+1-312-555-0105', '400 Michigan Ave',    'Chicago'),
        ('Freya Holst',   'freya@gmail.com',  '+1-617-555-0106', '22 Boylston St',      'Boston'),
        ('Noa Peretz',    'noa@gmail.com',    '+1-305-555-0107', '1 Ocean Dr',          'Miami'),
        ('Luca Ferrara',  'luca@gmail.com',   '+1-206-555-0108', '500 Pike St',         'Seattle'),
        ('Asha Nomvula',  'asha@gmail.com',   '+1-404-555-0109', '10 Peachtree Rd',     'Atlanta'),
        ('Orion Drake',   'orion@gmail.com',  '+1-702-555-0110', '3700 Las Vegas Blvd', 'Las Vegas'),
    ]
    c.executemany(
        "INSERT INTO customers (name, email, phone, address, city) VALUES (?,?,?,?,?)",
        customers
    )
    conn.commit()

    # Seed realistic orders over last 90 days
    statuses        = ['delivered', 'shipped', 'processing', 'pending', 'cancelled']
    payment_methods = ['card', 'card', 'paypal', 'apple_pay']
    product_weights = [9, 5, 7, 10, 6, 7, 6, 5, 4]

    c.execute("SELECT COUNT(*) FROM products")
    prod_count = c.fetchone()[0]

    for days_ago in range(90, 0, -1):
        num_orders = random.randint(1, 5)
        if days_ago < 30:
            num_orders = random.randint(3, 10)
        order_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')

        for _ in range(num_orders):
            customer_id = random.randint(1, 10)
            status      = random.choices(statuses, weights=[35, 20, 20, 15, 10])[0]
            payment     = random.choice(payment_methods)
            chosen      = random.choices(
                range(1, prod_count + 1),
                weights=product_weights[:prod_count],
                k=random.randint(1, 2)
            )
            items = []
            total = 0
            for pid in set(chosen):
                c.execute("SELECT price, sizes FROM products WHERE id=?", (pid,))
                prod = c.fetchone()
                if prod:
                    qty   = random.randint(1, 2)
                    sizes = json.loads(prod[1])
                    size  = random.choice(sizes)
                    items.append((pid, qty, prod[0], size))
                    total += prod[0] * qty

            if not items:
                continue

            c.execute(
                '''INSERT INTO orders (customer_id, total_amount, status, payment_method, shipping_address, created_at)
                   VALUES (?,?,?,?,?,?)''',
                (customer_id, total, status, payment, f"Address of customer {customer_id}", order_date)
            )
            oid = c.lastrowid
            for pid, qty, price, size in items:
                c.execute(
                    '''INSERT INTO order_items (order_id, product_id, quantity, price, size)
                       VALUES (?,?,?,?,?)''',
                    (oid, pid, qty, price, size)
                )

    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
# K-MEANS CLUSTERING
# ─────────────────────────────────────────────

def kmeans_clustering(data_points, k=3, max_iter=100):
    if len(data_points) < k:
        k = len(data_points)
    points    = [[float(p[0]), float(p[1])] for p in data_points]
    centroids = random.sample(points, k)
    for _ in range(max_iter):
        clusters    = [[] for _ in range(k)]
        assignments = []
        for point in points:
            distances   = [math.sqrt((point[0]-c[0])**2 + (point[1]-c[1])**2) for c in centroids]
            cluster_idx = distances.index(min(distances))
            assignments.append(cluster_idx)
            clusters[cluster_idx].append(point)
        new_centroids = []
        for i, cluster in enumerate(clusters):
            if cluster:
                new_centroids.append([sum(p[j] for p in cluster) / len(cluster) for j in range(2)])
            else:
                new_centroids.append(centroids[i])
        if new_centroids == centroids:
            break
        centroids = new_centroids
    return assignments, centroids

# ─────────────────────────────────────────────
# HELPER — get or create session ID
# ─────────────────────────────────────────────

def get_session_id():
    if 'session_id' not in session:
        session['session_id'] = str(random.randint(100000, 999999))
    return session['session_id']

# ─────────────────────────────────────────────
# ROUTES — MAIN WEBSITE
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/catalog")
def catalog():
    return render_template("index.html", section="catalog")

@app.route("/puffers")
def puffers():
    return render_template("index.html", section="puffers")

@app.route("/shells")
def shells():
    return render_template("index.html", section="shells")

# ─── CART PAGE ────────────────────────────────────────────────────────────────

@app.route("/cart")
def cart_page():
    session_id = get_session_id()
    conn  = get_db()
    items = conn.execute('''
        SELECT c.id, c.quantity, c.size, p.name, p.price, p.image_url, p.sku, p.stock, p.slug
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.session_id = ?
    ''', (session_id,)).fetchall()
    conn.close()
    total = sum(item['price'] * item['quantity'] for item in items)
    return render_template('cart.html', items=items, total=total)

# ─── CHECKOUT ─────────────────────────────────────────────────────────────────

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    session_id = get_session_id()
    conn       = get_db()

    if request.method == "POST":
        data     = request.form
        existing = conn.execute(
            "SELECT id FROM customers WHERE email=?", (data['email'],)
        ).fetchone()

        if existing:
            customer_id = existing['id']
            conn.execute(
                "UPDATE customers SET name=?, phone=?, address=?, city=? WHERE id=?",
                (data['name'], data.get('phone', ''), data.get('address', ''), data.get('city', ''), existing['id'])
            )
        else:
            conn.execute(
                "INSERT INTO customers (name, email, phone, address, city) VALUES (?,?,?,?,?)",
                (data['name'], data['email'], data.get('phone', ''), data.get('address', ''), data.get('city', ''))
            )
            customer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        items = conn.execute('''
            SELECT c.*, p.price FROM cart c JOIN products p ON c.product_id = p.id
            WHERE c.session_id = ?
        ''', (session_id,)).fetchall()

        if not items:
            conn.close()
            return redirect(url_for('cart_page'))

        total    = sum(item['price'] * item['quantity'] for item in items)
        shipping = data.get('address', '') + ', ' + data.get('city', '')

        conn.execute(
            '''INSERT INTO orders (customer_id, total_amount, status, payment_method, shipping_address)
               VALUES (?,?,?,?,?)''',
            (customer_id, total, 'processing', data.get('payment', 'card'), shipping)
        )
        order_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for item in items:
            conn.execute(
                '''INSERT INTO order_items (order_id, product_id, quantity, price, size)
                   VALUES (?,?,?,?,?)''',
                (order_id, item['product_id'], item['quantity'], item['price'], item['size'])
            )
            conn.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (item['quantity'], item['product_id'])
            )

        conn.execute("DELETE FROM cart WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('order_success', order_id=order_id))

    items = conn.execute('''
        SELECT c.id, c.quantity, c.size, p.name, p.price, p.image_url, p.sku
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.session_id = ?
    ''', (session_id,)).fetchall()
    conn.close()
    total = sum(item['price'] * item['quantity'] for item in items)
    return render_template('checkout.html', items=items, total=total)

# ─── ORDER SUCCESS ────────────────────────────────────────────────────────────

@app.route("/order/<int:order_id>")
def order_success(order_id):
    conn  = get_db()
    order = conn.execute('''
        SELECT o.*, c.name as customer_name, c.email, c.city
        FROM orders o JOIN customers c ON o.customer_id = c.id
        WHERE o.id = ?
    ''', (order_id,)).fetchone()
    items = conn.execute('''
        SELECT oi.*, p.name, p.image_url, p.sku
        FROM order_items oi JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    conn.close()
    return render_template('order_success.html', order=order, items=items)

# ─── ANALYTICS DASHBOARD ─────────────────────────────────────────────────────

@app.route("/analytics")
def analytics():
    return render_template("analytics.html")

# ─────────────────────────────────────────────
# API ROUTES — NEWSLETTER
# ─────────────────────────────────────────────

@app.route("/api/newsletter", methods=["POST"])
def newsletter():
    data  = request.get_json()
    email = data.get("email", "").strip()
    if not email or "@" not in email:
        return jsonify({"success": False, "message": "Invalid email address."}), 400
    print(f"[COLD DROP LIST] New signup: {email}")
    return jsonify({"success": True, "message": "You're in the Cold Drop. We'll hit you when it drops."})

# ─────────────────────────────────────────────
# API ROUTES — CART
# ─────────────────────────────────────────────

@app.route("/api/cart/add", methods=["POST"])
def cart_add():
    """
    Accepts JSON: { slug, size, qty }  OR  { product_id, size, qty }
    Matches or creates a cart row for this session, then returns the new total count.
    """
    session_id = get_session_id()
    data       = request.get_json(silent=True) or {}
    size       = data.get("size", "M")
    qty        = max(1, int(data.get("qty", 1)))

    # Resolve product_id from slug or direct id
    product_id = data.get("id") or data.get("product_id")
    if not product_id:
        slug = data.get("slug", "").strip()
        if not slug:
            return jsonify({"success": False, "message": "No product specified."}), 400
        conn = get_db()
        row  = conn.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone()
        conn.close()
        if not row:
            return jsonify({"success": False, "message": f"Product '{slug}' not found."}), 404
        product_id = row['id']

    conn     = get_db()
    existing = conn.execute(
        "SELECT id, quantity FROM cart WHERE session_id=? AND product_id=? AND size=?",
        (session_id, product_id, size)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE cart SET quantity = quantity + ? WHERE id = ?",
            (qty, existing['id'])
        )
    else:
        conn.execute(
            "INSERT INTO cart (session_id, product_id, quantity, size) VALUES (?,?,?,?)",
            (session_id, product_id, qty, size)
        )

    conn.commit()
    count = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM cart WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    conn.close()
    return jsonify({"success": True, "cart_count": int(count)})

@app.route("/api/cart", methods=["GET"])
def cart_get():
    session_id = get_session_id()
    conn       = get_db()
    items      = conn.execute('''
        SELECT c.id, c.quantity, c.size, p.name, p.price, p.image_url, p.sku, p.slug
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.session_id = ?
    ''', (session_id,)).fetchall()
    conn.close()
    items_list = [dict(i) for i in items]
    total      = sum(i['price'] * i['quantity'] for i in items_list)
    return jsonify({
        "items": items_list,
        "total": round(total, 2),
        "count": int(sum(i['quantity'] for i in items_list))
    })

@app.route("/api/cart/update/<int:item_id>", methods=["PATCH"])
def update_cart_item(item_id):
    """Update quantity of a specific cart line item."""
    data = request.get_json(silent=True) or {}
    qty  = int(data.get("qty", 1))
    conn = get_db()
    if qty <= 0:
        conn.execute("DELETE FROM cart WHERE id = ?", (item_id,))
    else:
        conn.execute("UPDATE cart SET quantity = ? WHERE id = ?", (qty, item_id))
    conn.commit()
    session_id = get_session_id()
    count = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM cart WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    conn.close()
    return jsonify({"success": True, "cart_count": int(count)})

@app.route("/api/cart/remove/<int:item_id>", methods=["DELETE"])
def remove_from_cart(item_id):
    conn = get_db()
    conn.execute("DELETE FROM cart WHERE id = ?", (item_id,))
    conn.commit()
    session_id = get_session_id()
    count = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM cart WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    conn.close()
    return jsonify({"success": True, "cart_count": int(count)})

@app.route("/api/cart/clear", methods=["POST"])
def cart_clear():
    session_id = get_session_id()
    conn       = get_db()
    conn.execute("DELETE FROM cart WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/cart/count")
def cart_count():
    """Returns the total quantity of items in the current session's cart."""
    session_id = get_session_id()
    conn       = get_db()
    count      = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM cart WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    conn.close()
    return jsonify({"count": int(count)})

# ─────────────────────────────────────────────
# API ROUTES — PRODUCTS
# ─────────────────────────────────────────────

@app.route("/api/products", methods=["GET"])
def products_list():
    category = request.args.get("category")
    sort     = request.args.get("sort", "newest")
    conn     = get_db()
    query    = "SELECT p.*, c.name as cat_name FROM products p JOIN categories c ON p.category_id = c.id WHERE 1=1"
    params   = []
    if category:
        query += " AND c.slug = ?"
        params.append(category)
    order_map = {"newest": "p.id DESC", "price": "p.price ASC", "price_high": "p.price DESC"}
    query += f" ORDER BY {order_map.get(sort, 'p.id DESC')}"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/products/<product_id>", methods=["GET"])
def product_detail_api(product_id):
    conn    = get_db()
    product = conn.execute(
        "SELECT p.*, c.name as cat_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.slug=?",
        (product_id,)
    ).fetchone()
    conn.close()
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(dict(product))

# ─────────────────────────────────────────────
# API ROUTES — ANALYTICS
# ─────────────────────────────────────────────

@app.route("/api/analytics/summary")
def analytics_summary():
    conn = get_db()
    revenue         = conn.execute("SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE status != 'cancelled'").fetchone()[0]
    total_orders    = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    total_products  = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    avg_order       = conn.execute("SELECT COALESCE(AVG(total_amount),0) FROM orders WHERE status != 'cancelled'").fetchone()[0]
    pending         = conn.execute("SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0]
    shipped         = conn.execute("SELECT COUNT(*) FROM orders WHERE status='shipped'").fetchone()[0]
    delivered       = conn.execute("SELECT COUNT(*) FROM orders WHERE status='delivered'").fetchone()[0]
    conn.close()
    return jsonify({
        'revenue':   round(revenue, 2),
        'orders':    total_orders,
        'customers': total_customers,
        'products':  total_products,
        'avg_order': round(avg_order, 2),
        'pending':   pending,
        'shipped':   shipped,
        'delivered': delivered,
    })

@app.route("/api/analytics/top-products")
def top_products():
    conn = get_db()
    rows = conn.execute('''
        SELECT p.name, p.slug, p.sku, c.name as category,
               SUM(oi.quantity) as units_sold,
               SUM(oi.quantity * oi.price) as revenue,
               p.stock, p.price
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status != 'cancelled'
        GROUP BY p.id ORDER BY revenue DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/analytics/category-sales")
def category_sales():
    conn = get_db()
    rows = conn.execute('''
        SELECT c.name as category,
               SUM(oi.quantity * oi.price) as revenue,
               SUM(oi.quantity) as units,
               COUNT(DISTINCT o.id) as orders
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status != 'cancelled'
        GROUP BY c.id ORDER BY revenue DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/analytics/order-trends")
def order_trends():
    conn = get_db()
    rows = conn.execute('''
        SELECT DATE(created_at) as date,
               COUNT(*) as orders,
               SUM(total_amount) as revenue
        FROM orders
        WHERE status != 'cancelled'
        AND created_at >= DATE('now', '-30 days')
        GROUP BY DATE(created_at) ORDER BY date ASC
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/analytics/stock-status")
def stock_status():
    conn = get_db()
    rows = conn.execute('''
        SELECT name, sku, stock,
        CASE
            WHEN stock = 0   THEN 'Out of Stock'
            WHEN stock <= 15 THEN 'Low Stock'
            WHEN stock <= 30 THEN 'Medium Stock'
            ELSE                  'In Stock'
        END as status
        FROM products ORDER BY stock ASC
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/analytics/clustering")
def product_clustering():
    conn = get_db()
    rows = conn.execute('''
        SELECT p.id, p.name, p.sku, p.category_id,
               COALESCE(SUM(oi.quantity), 0) as units_sold,
               COALESCE(SUM(oi.quantity * oi.price), 0) as revenue,
               p.price, p.stock
        FROM products p
        LEFT JOIN order_items oi ON p.id = oi.product_id
        LEFT JOIN orders o ON oi.order_id = o.id AND o.status != 'cancelled'
        GROUP BY p.id
    ''').fetchall()
    conn.close()

    products_data = [dict(r) for r in rows]
    if len(products_data) < 3:
        return jsonify({'clusters': [], 'products': products_data})

    max_units = max(p['units_sold'] for p in products_data) or 1
    max_rev   = max(p['revenue']   for p in products_data) or 1
    points    = [(p['units_sold'] / max_units * 100, p['revenue'] / max_rev * 100) for p in products_data]

    assignments, centroids = kmeans_clustering(points, k=3)

    cluster_stats = defaultdict(lambda: {'units': 0, 'revenue': 0, 'count': 0})
    for prod, cluster in zip(products_data, assignments):
        cluster_stats[cluster]['units']   += prod['units_sold']
        cluster_stats[cluster]['revenue'] += prod['revenue']
        cluster_stats[cluster]['count']   += 1

    sorted_clusters = sorted(cluster_stats.keys(), key=lambda cl: cluster_stats[cl]['revenue'])
    labels = {}
    if len(sorted_clusters) >= 3:
        labels = {sorted_clusters[0]: 'Low Performer', sorted_clusters[1]: 'Mid Performer', sorted_clusters[2]: 'Top Performer'}
    elif len(sorted_clusters) == 2:
        labels = {sorted_clusters[0]: 'Low Performer', sorted_clusters[1]: 'Top Performer'}
    else:
        labels = {sorted_clusters[0]: 'Mid Performer'}

    result = []
    for prod, cluster, point in zip(products_data, assignments, points):
        result.append({
            **prod,
            'cluster':            cluster,
            'cluster_label':      labels.get(cluster, 'Mid Performer'),
            'normalized_units':   round(point[0], 2),
            'normalized_revenue': round(point[1], 2),
        })

    return jsonify({'products': result, 'centroids': centroids})

@app.route("/api/analytics/recent-orders")
def recent_orders():
    conn = get_db()
    rows = conn.execute('''
        SELECT o.id, o.total_amount, o.status, o.created_at, o.payment_method,
               c.name as customer_name, c.city
        FROM orders o JOIN customers c ON o.customer_id = c.id
        ORDER BY o.created_at DESC LIMIT 10
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/analytics/customer-clusters")
def customer_clusters():
    conn = get_db()
    rows = conn.execute('''
        SELECT c.id, c.name, c.city,
               COUNT(DISTINCT o.id)             as order_count,
               COALESCE(SUM(o.total_amount), 0) as total_spent,
               COALESCE(AVG(o.total_amount), 0) as avg_order_value
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        WHERE o.status != 'cancelled'
          AND o.created_at >= DATE('now', '-30 days')
        GROUP BY c.id ORDER BY total_spent DESC
    ''').fetchall()
    conn.close()
    customers_data = [dict(r) for r in rows]

    if not customers_data:
        return jsonify({'customers': [], 'summary': {}})

    if len(customers_data) < 3:
        for cust in customers_data:
            if cust['total_spent'] > 5000:
                cust['segment'] = 'High Value'
            elif cust['total_spent'] > 2000:
                cust['segment'] = 'Regular Buyer'
            else:
                cust['segment'] = 'Occasional Buyer'
            cust['norm_orders'] = 0.0
            cust['norm_spent']  = 0.0
        summary = defaultdict(lambda: {'count': 0, 'total_spent': 0.0, 'order_count': 0})
        for cust in customers_data:
            seg = cust['segment']
            summary[seg]['count']       += 1
            summary[seg]['total_spent'] += cust['total_spent']
            summary[seg]['order_count'] += cust['order_count']
        summary_out = {
            seg: {
                'count':      v['count'],
                'avg_spent':  round(v['total_spent'] / v['count'], 2) if v['count'] else 0,
                'avg_orders': round(v['order_count']  / v['count'], 2) if v['count'] else 0,
            }
            for seg, v in summary.items()
        }
        return jsonify({'customers': customers_data, 'summary': summary_out})

    max_orders = max(c['order_count'] for c in customers_data) or 1
    max_spent  = max(c['total_spent'] for c in customers_data) or 1
    points     = [(c['order_count'] / max_orders * 100, c['total_spent'] / max_spent * 100) for c in customers_data]

    k = min(3, len(customers_data))
    assignments, _ = kmeans_clustering(points, k=k)

    cluster_spend   = defaultdict(list)
    for cust, cluster in zip(customers_data, assignments):
        cluster_spend[cluster].append(cust['total_spent'])

    cluster_avg     = {cl: sum(s) / len(s) for cl, s in cluster_spend.items()}
    sorted_clusters = sorted(cluster_avg.keys(), key=lambda cl: cluster_avg[cl])
    segment_names   = ['Occasional Buyer', 'Regular Buyer', 'High Value']
    label_map       = {cl: segment_names[min(i, 2)] for i, cl in enumerate(sorted_clusters)}

    summary = defaultdict(lambda: {'count': 0, 'total_spent': 0.0, 'order_count': 0})
    result  = []
    for cust, cluster, point in zip(customers_data, assignments, points):
        seg = label_map.get(cluster, 'Regular Buyer')
        summary[seg]['count']       += 1
        summary[seg]['total_spent'] += cust['total_spent']
        summary[seg]['order_count'] += cust['order_count']
        result.append({
            **cust,
            'segment':      seg,
            'norm_orders':  round(point[0], 2),
            'norm_spent':   round(point[1], 2),
        })

    summary_out = {
        seg: {
            'count':      v['count'],
            'avg_spent':  round(v['total_spent'] / v['count'], 2) if v['count'] else 0,
            'avg_orders': round(v['order_count']  / v['count'], 2) if v['count'] else 0,
        }
        for seg, v in summary.items()
    }
    return jsonify({'customers': result, 'summary': summary_out})

# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
# At the bottom of app.py, replace the if __name__ block with:
init_db()
seed_data()

if __name__ == '__main__':
    app.run(debug=True, port=5000)