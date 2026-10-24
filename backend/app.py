"""
Mini E-commerce Store — Backend API
Fundamentals of Cloud Computing (FoCC) Lab 2

This Flask application provides:
- Product catalog management
- Shopping cart state stored in Redis
- Health checks (Liveness & Readiness)
- Prometheus metrics endpoint (/metrics)
- Controlled CPU load testing endpoint (/api/test-load)
"""

import os
import time
import math
import hashlib
from datetime import datetime
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
# pyrefly: ignore[missing-import]
import redis
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Initialize Flask application
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing for dev flexibility

# -----------------------------------------------------------------------------
# Configuration from Environment Variables
# -----------------------------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
ENABLE_TEST_LOAD = os.getenv("ENABLE_TEST_LOAD", "false").lower() == "true"
PORT = int(os.getenv("PORT", "5000"))

# Initialize Redis client with reasonable timeouts to avoid hanging requests
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_connect_timeout=2.0,
    socket_timeout=2.0,
)

DEMO_CART_KEY = "cart:demo"

# -----------------------------------------------------------------------------
# Prometheus Metrics Configuration
# -----------------------------------------------------------------------------
# Total HTTP request counter by method, path, and HTTP status
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the backend",
    ["method", "endpoint", "status"]
)

# Latency histogram in seconds (with buckets tailored to cloud web APIs)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# HTTP error counter (4xx and 5xx)
HTTP_REQUEST_ERRORS_TOTAL = Counter(
    "http_request_errors_total",
    "Total HTTP 4xx and 5xx errors returned",
    ["method", "endpoint", "status"]
)


@app.before_request
def start_timer():
    """Record request arrival time for latency calculation."""
    request.start_time = time.time()


@app.after_request
def record_metrics(response):
    """Update Prometheus metrics after request finishes."""
    if hasattr(request, "start_time"):
        duration = time.time() - request.start_time
        # Simplify endpoint label to prevent metric cardinality explosion
        endpoint = request.url_rule.rule if request.url_rule else request.path
        status_code = str(response.status_code)
        method = request.method

        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status_code).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)

        if response.status_code >= 400:
            HTTP_REQUEST_ERRORS_TOTAL.labels(method=method, endpoint=endpoint, status=status_code).inc()

    return response


# -----------------------------------------------------------------------------
# Sample Product Catalog (8 Diverse Tech & Student Essentials)
# -----------------------------------------------------------------------------
PRODUCTS = [
    {
        "id": "prod-1",
        "name": "Cloud Architecture Blueprint Poster",
        "category": "Accessories",
        "description": "High-res glossy poster covering distributed systems, microservices, and Kubernetes patterns.",
        "price": 19.99,
        "image": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "prod-2",
        "name": "Wireless Noise-Cancelling Headphones",
        "category": "Electronics",
        "description": "Premium active noise cancellation designed for deep coding sessions and study marathons.",
        "price": 89.99,
        "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "prod-3",
        "name": "Mechanical Keyboard (RGB Backlit)",
        "category": "Electronics",
        "description": "Compact 75% mechanical keyboard with tactile blue switches and custom RGB profiles.",
        "price": 64.99,
        "image": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "prod-4",
        "name": "Ergonomic Memory Foam Wrist Rest",
        "category": "Accessories",
        "description": "Contoured memory foam support reduces wrist fatigue during extended programming sessions.",
        "price": 14.99,
        "image": "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "prod-5",
        "name": "Kubernetes & Cloud Native Notebook",
        "category": "Stationery",
        "description": "Dot-grid durable notebook featuring quick Kubernetes kubectl cheat-sheets inside the cover.",
        "price": 12.99,
        "image": "https://images.unsplash.com/photo-1544717305-2782549b5136?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "prod-6",
        "name": "Ultra-Slim USB-C Multi-Port Hub",
        "category": "Electronics",
        "description": "7-in-1 aluminum hub with 4K HDMI, 100W Power Delivery, SD Card reader, and 3x USB 3.0 ports.",
        "price": 29.99,
        "image": "https://images.unsplash.com/photo-1544652478-6653e09f18a2?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "prod-7",
        "name": "Python Data Science Handbook (Quick Ref)",
        "category": "Books",
        "description": "A student-friendly companion covering Pandas, NumPy, Scikit-learn, and cloud data workflows.",
        "price": 24.99,
        "image": "https://images.unsplash.com/photo-1532012164546-f432f2e3777f?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "prod-8",
        "name": "Thermal Insulated Stainless Steel Mug",
        "category": "Lifestyle",
        "description": "Double-wall vacuum insulated coffee tumbler that keeps drinks hot for 6 hours.",
        "price": 18.99,
        "image": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=600&q=80"
    }
]

PRODUCTS_BY_ID = {p["id"]: p for p in PRODUCTS}


# -----------------------------------------------------------------------------
# Cart Helper Functions
# -----------------------------------------------------------------------------
def get_cart_data():
    """Fetch cart entries from Redis and compile total calculations."""
    try:
        raw_items = redis_client.hgetall(DEMO_CART_KEY)
    except redis.RedisError as e:
        raise RuntimeError(f"Redis unavailable: {e}")

    items = []
    subtotal = 0.0
    total_items = 0

    for prod_id, qty_str in raw_items.items():
        try:
            quantity = int(qty_str)
        except ValueError:
            continue

        if quantity > 0 and prod_id in PRODUCTS_BY_ID:
            prod = PRODUCTS_BY_ID[prod_id]
            item_total = round(prod["price"] * quantity, 2)
            subtotal += item_total
            total_items += quantity
            items.append({
                "product_id": prod["id"],
                "name": prod["name"],
                "category": prod["category"],
                "price": prod["price"],
                "image": prod["image"],
                "quantity": quantity,
                "item_total": item_total
            })

    # Sort items predictably by name
    items.sort(key=lambda x: x["name"])

    subtotal = round(subtotal, 2)
    tax = round(subtotal * 0.08, 2)  # 8% sample sales tax
    total = round(subtotal + tax, 2)

    return {
        "items": items,
        "total_items": total_items,
        "subtotal": subtotal,
        "tax": tax,
        "shipping": 0.0,
        "total": total
    }


# -----------------------------------------------------------------------------
# REST API Endpoints
# -----------------------------------------------------------------------------
@app.route("/api/products", methods=["GET"])
def get_products():
    """Return the complete product catalog."""
    return jsonify({
        "count": len(PRODUCTS),
        "products": PRODUCTS
    }), 200


@app.route("/api/cart", methods=["GET"])
def get_cart():
    """Return the current demo shopping cart from Redis."""
    try:
        cart = get_cart_data()
        return jsonify(cart), 200
    except RuntimeError as e:
        return jsonify({"error": str(e), "message": "Failed to read cart from Redis"}), 503


@app.route("/api/cart", methods=["POST"])
def update_cart():
    """
    Add a product or update its quantity in the cart.
    Expected JSON body:
      {
        "product_id": "prod-1",
        "quantity": 2
      }
    """
    data = request.get_json(silent=True)
    if not data or "product_id" not in data:
        return jsonify({"error": "Missing 'product_id' in request body."}), 400

    product_id = str(data["product_id"])
    if product_id not in PRODUCTS_BY_ID:
        return jsonify({"error": f"Product with ID '{product_id}' not found."}), 404

    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "'quantity' must be an integer."}), 400

    try:
        if quantity <= 0:
            # Remove item if quantity is zero or negative
            redis_client.hdel(DEMO_CART_KEY, product_id)
        else:
            # Update quantity in Redis Hash
            redis_client.hset(DEMO_CART_KEY, product_id, quantity)

        cart = get_cart_data()
        return jsonify({
            "message": "Cart updated successfully.",
            "cart": cart
        }), 200
    except redis.RedisError as e:
        return jsonify({"error": f"Redis storage error: {e}"}), 503


@app.route("/api/cart/<product_id>", methods=["DELETE"])
def remove_from_cart(product_id):
    """Remove a product completely from the demo cart."""
    try:
        redis_client.hdel(DEMO_CART_KEY, product_id)
        cart = get_cart_data()
        return jsonify({
            "message": f"Product '{product_id}' removed from cart.",
            "cart": cart
        }), 200
    except redis.RedisError as e:
        return jsonify({"error": f"Redis storage error: {e}"}), 503


# -----------------------------------------------------------------------------
# Health and Diagnostics Endpoints
# -----------------------------------------------------------------------------
@app.route("/health/live", methods=["GET"])
def health_live():
    """
    Liveness Check:
    Verifies that the Flask process is running and able to handle HTTP requests.
    Notice: Does NOT check Redis to prevent unnecessary pod restart cascades.
    """
    return jsonify({
        "status": "alive",
        "service": "mini-ecommerce-backend",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@app.route("/health/ready", methods=["GET"])
def health_ready():
    """
    Readiness Check:
    Verifies that the application and its critical dependencies (Redis)
    are ready to accept user traffic.
    Returns 200 if Redis is reachable, 503 if Redis is unreachable.
    """
    try:
        # Ping Redis with quick timeout
        redis_ok = redis_client.ping()
        if redis_ok:
            return jsonify({
                "status": "ready",
                "redis": "connected",
                "dependencies": {
                    "redis": "ok"
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }), 200
        else:
            return jsonify({
                "status": "not_ready",
                "error": "Redis ping returned false",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }), 503
    except Exception as e:
        return jsonify({
            "status": "not_ready",
            "error": f"Redis unreachable: {str(e)}",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 503


@app.route("/metrics", methods=["GET"])
def metrics():
    """
    Prometheus-compatible metrics exposition endpoint.
    Scraped by Prometheus or Azure Monitor Managed Prometheus.
    """
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


# -----------------------------------------------------------------------------
# Controlled CPU Load Testing Endpoint
# -----------------------------------------------------------------------------
@app.route("/api/test-load", methods=["GET"])
def test_load():
    """
    Controlled CPU-load endpoint for authorized lab testing only.
    - Validates duration (0.1s to 5.0s).
    - Disabled by default outside lab environment (requires ENABLE_TEST_LOAD=true).
    """
    if not ENABLE_TEST_LOAD:
        return jsonify({
            "error": "Controlled test-load endpoint is disabled.",
            "instructions": (
                "To enable for FoCC Lab 2 testing, set environment variable "
                "ENABLE_TEST_LOAD=true in docker-compose.yml or k8s/configmap.yaml."
            )
        }), 403

    raw_duration = request.args.get("duration", "2")
    try:
        duration = float(raw_duration)
    except ValueError:
        return jsonify({"error": "Query parameter 'duration' must be a valid number of seconds."}), 400

    if duration < 0.1:
        return jsonify({"error": "Duration must be at least 0.1 seconds."}), 400

    # Strict safety constraint: limit to at most 5 seconds per request
    if duration > 5.0:
        return jsonify({"error": "Duration exceeds maximum lab limit of 5.0 seconds per request."}), 400

    start_time = time.time()
    iterations = 0

    # CPU-bound calculation loop: calculates cryptographic hashes and square roots
    # until the specified time duration has elapsed.
    while (time.time() - start_time) < duration:
        _ = hashlib.sha256(f"focc-lab-2-{iterations}".encode()).hexdigest()
        _ = math.sqrt(iterations + 1.0) * math.sin(iterations + 1.0)
        iterations += 1

    actual_duration = time.time() - start_time

    return jsonify({
        "status": "completed",
        "message": "Controlled CPU load test executed successfully.",
        "requested_duration_seconds": duration,
        "actual_duration_seconds": round(actual_duration, 4),
        "iterations": iterations
    }), 200


if __name__ == "__main__":
    print(f"Starting Mini E-commerce Backend on port {PORT}...")
    print(f"Redis target: {REDIS_HOST}:{REDIS_PORT}")
    print(f"Controlled test load enabled: {ENABLE_TEST_LOAD}")
    app.run(host="0.0.0.0", port=PORT)
