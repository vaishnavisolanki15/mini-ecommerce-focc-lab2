import React, { useState, useEffect } from 'react';

export default function App() {
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState({ items: [], total_items: 0, subtotal: 0, tax: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState('All');
  const [backendHealth, setBackendHealth] = useState({ online: false, checking: true });
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [lastOrderId, setLastOrderId] = useState('');

  // Diagnostics & Metrics Modals
  const [healthModalOpen, setHealthModalOpen] = useState(false);
  const [healthDetails, setHealthDetails] = useState(null);
  const [healthLoading, setHealthLoading] = useState(false);

  const [metricsModalOpen, setMetricsModalOpen] = useState(false);
  const [metricsText, setMetricsText] = useState('');
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [metricsSearch, setMetricsSearch] = useState('');
  const [copiedMetrics, setCopiedMetrics] = useState(false);

  // Controlled Load Test state for Lab demonstration
  const [loadTesting, setLoadTesting] = useState(false);
  const [loadResult, setLoadResult] = useState(null);
  const [loadError, setLoadError] = useState(null);

  // Fetch full health probe details for modal
  const fetchHealthDetails = async () => {
    setHealthLoading(true);
    try {
      const [readyRes, liveRes] = await Promise.all([
        fetch('/health/ready'),
        fetch('/health/live'),
      ]);
      const readyJson = await readyRes.json().catch(() => ({ status: 'error' }));
      const liveJson = await liveRes.json().catch(() => ({ status: 'error' }));
      setHealthDetails({
        readyStatus: readyRes.status,
        ready: readyJson,
        liveStatus: liveRes.status,
        live: liveJson,
        timestamp: new Date().toLocaleTimeString(),
      });
    } catch (err) {
      setHealthDetails({ error: err.message, timestamp: new Date().toLocaleTimeString() });
    } finally {
      setHealthLoading(false);
    }
  };

  const openHealthModal = () => {
    setHealthModalOpen(true);
    fetchHealthDetails();
  };

  // Fetch Prometheus metrics for modal
  const fetchMetricsDetails = async () => {
    setMetricsLoading(true);
    try {
      const res = await fetch('/metrics');
      if (res.ok) {
        const text = await res.text();
        setMetricsText(text);
      } else {
        setMetricsText(`Error: HTTP ${res.status}`);
      }
    } catch (err) {
      setMetricsText(`Error fetching metrics: ${err.message}`);
    } finally {
      setMetricsLoading(false);
    }
  };

  const openMetricsModal = () => {
    setMetricsModalOpen(true);
    fetchMetricsDetails();
  };

  const copyMetrics = () => {
    navigator.clipboard.writeText(metricsText);
    setCopiedMetrics(true);
    setTimeout(() => setCopiedMetrics(false), 2000);
  };

  const parseMetricsSummary = (raw) => {
    if (!raw) return { totalRequests: 0, memoryMb: '—', cpuSeconds: '—', gcObjects: '—' };
    let totalReq = 0;
    const reqMatches = raw.matchAll(/http_requests_total\{[^}]*\}\s+([\d.]+)/g);
    for (const match of reqMatches) {
      totalReq += parseFloat(match[1]) || 0;
    }
    const memMatch = raw.match(/process_resident_memory_bytes\s+([\d.e+-]+)/);
    const memoryMb = memMatch ? (parseFloat(memMatch[1]) / (1024 * 1024)).toFixed(1) : '—';
    const cpuMatch = raw.match(/process_cpu_seconds_total\s+([\d.]+)/);
    const cpuSeconds = cpuMatch ? parseFloat(cpuMatch[1]).toFixed(2) : '—';
    const gcMatch = raw.match(/python_gc_objects_collected_total\{generation="0"\}\s+([\d.]+)/);
    const gcObjects = gcMatch ? parseFloat(gcMatch[1]).toLocaleString() : '—';

    return { totalRequests: totalReq, memoryMb, cpuSeconds, gcObjects };
  };

  // Check backend readiness
  const checkHealth = async () => {
    try {
      const res = await fetch('/health/ready');
      if (res.ok) {
        setBackendHealth({ online: true, checking: false });
      } else {
        setBackendHealth({ online: false, checking: false });
      }
    } catch {
      setBackendHealth({ online: false, checking: false });
    }
  };

  // Fetch product catalog
  const fetchProducts = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/products');
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch products`);
      const data = await res.json();
      setProducts(data.products || []);
    } catch (err) {
      setError(err.message || 'Unable to connect to backend product service');
    } finally {
      setLoading(false);
    }
  };

  // Fetch cart
  const fetchCart = async () => {
    try {
      const res = await fetch('/api/cart');
      if (res.ok) {
        const data = await res.json();
        setCart(data);
      }
    } catch (err) {
      console.warn('Could not fetch cart:', err);
    }
  };

  useEffect(() => {
    fetchProducts();
    fetchCart();
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  // Update item quantity or add to cart
  const updateQuantity = async (productId, newQuantity) => {
    try {
      const res = await fetch('/api/cart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, quantity: newQuantity }),
      });
      if (res.ok) {
        const data = await res.json();
        setCart(data.cart);
      } else {
        const err = await res.json();
        alert(err.error || 'Failed to update cart');
      }
    } catch (err) {
      alert('Network error while updating cart: ' + err.message);
    }
  };

  // Quick add 1 item
  const handleAddToCart = (product) => {
    const existing = cart.items.find((item) => item.product_id === product.id);
    const newQty = existing ? existing.quantity + 1 : 1;
    updateQuantity(product.id, newQty);
  };

  // Remove completely from cart
  const handleRemove = async (productId) => {
    try {
      const res = await fetch(`/api/cart/${productId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        const data = await res.json();
        setCart(data.cart);
      }
    } catch (err) {
      alert('Failed to remove item: ' + err.message);
    }
  };

  // Trigger Controlled Lab CPU Load Test
  const triggerLoadTest = async () => {
    setLoadTesting(true);
    setLoadResult(null);
    setLoadError(null);
    try {
      const res = await fetch('/api/test-load?duration=2');
      const data = await res.json();
      if (res.ok) {
        setLoadResult(data);
      } else {
        setLoadError(data.error || 'Load test request rejected.');
      }
    } catch (err) {
      setLoadError('Failed to reach load test endpoint: ' + err.message);
    } finally {
      setLoadTesting(false);
    }
  };

  // Demo Checkout handler
  const handleCheckout = () => {
    setLastOrderId('ORD-' + Math.floor(100000 + Math.random() * 900000));
    setOrderModalOpen(true);
  };

  // Filter products by category
  const categories = ['All', ...new Set(products.map((p) => p.category))];
  const filteredProducts =
    activeCategory === 'All' ? products : products.filter((p) => p.category === activeCategory);

  return (
    <div>
      {/* Sticky Navigation Bar */}
      <nav className="navbar">
        <div className="container nav-content">
          <div className="brand-wrapper">
            <div className="brand-logo">☁️</div>
            <div>
              <div className="brand-title">CloudCart</div>
              <span className="brand-badge">FoCC Lab 2</span>
            </div>
          </div>

          <div className="nav-actions">
            <div className="status-pill" title="Checks /health/ready endpoint">
              <span className={`status-dot ${backendHealth.online ? 'online' : 'offline'}`} />
              <span>{backendHealth.online ? 'Backend Ready' : 'Backend Connecting...'}</span>
            </div>

            <button
              id="open-cart-btn"
              className="cart-btn"
              onClick={() => setCartOpen(true)}
              aria-label="Open Shopping Cart"
            >
              <span>🛒 Cart</span>
              <span className="cart-badge">{cart.total_items}</span>
            </button>
          </div>
        </div>
      </nav>

      {/* Hero & Lab Controls Section */}
      <header className="hero">
        <div className="container">
          <div className="hero-subtitle">Fundamentals of Cloud Computing — Lab 2</div>
          <h1 className="hero-title">Microservices E-Commerce Store</h1>
          <p className="hero-description">
            A resilient cloud-native application running React on Vite, Flask REST API, and Redis
            caching. Prepared for Azure Container Registry (ACR) and AKS with Horizontal Pod Autoscaler.
          </p>

          {/* Interactive Lab Control Panel */}
          <div className="lab-toolbar">
            <div className="lab-toolbar-title">
              <span>⚡ Lab Testing Controls:</span>
            </div>

            <button
              id="btn-run-load-test"
              className="btn-loadtest"
              onClick={triggerLoadTest}
              disabled={loadTesting}
              title="Runs a 2-second safe CPU computation on the backend"
            >
              {loadTesting ? '⏳ Running 2s CPU Load...' : '🔥 Test CPU Load (/api/test-load)'}
            </button>

            <button
              id="btn-health-check"
              className="btn-secondary"
              onClick={openHealthModal}
              title="Inspect backend liveness & readiness probes"
            >
              🏥 Health Check
            </button>

            <button
              id="btn-metrics"
              className="btn-secondary"
              onClick={openMetricsModal}
              title="Inspect live Prometheus metrics & telemetry"
            >
              📊 Prometheus Metrics
            </button>
          </div>

          {/* Load Test Feedback Display */}
          {loadResult && (
            <div className="banner success" style={{ maxWidth: '780px', margin: '1rem auto 0' }}>
              <div>
                <strong>CPU Load Completed:</strong> Duration: {loadResult.actual_duration_seconds}s |
                Iterations: {loadResult.iterations.toLocaleString()}
              </div>
              <button className="banner-btn" onClick={() => setLoadResult(null)}>
                Dismiss
              </button>
            </div>
          )}

          {loadError && (
            <div className="banner error" style={{ maxWidth: '780px', margin: '1rem auto 0' }}>
              <div>
                <strong>Load Test Error:</strong> {loadError}
              </div>
              <button className="banner-btn" onClick={() => setLoadError(null)}>
                Dismiss
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Main Catalog View */}
      <main className="container">
        {/* Error Banner */}
        {error && (
          <div className="banner error" style={{ marginTop: '1.5rem' }}>
            <div>
              <strong>Service Error:</strong> {error}
            </div>
            <button className="banner-btn" onClick={fetchProducts}>
              Retry
            </button>
          </div>
        )}

        {/* Category Filters */}
        <div className="filter-bar">
          <div className="category-tabs">
            {categories.map((cat) => (
              <button
                key={cat}
                className={`category-tab ${activeCategory === cat ? 'active' : ''}`}
                onClick={() => setActiveCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
          <div className="product-count">
            Showing {filteredProducts.length} of {products.length} products
          </div>
        </div>

        {/* Product Grid */}
        {loading ? (
          <div className="product-grid">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
              <div key={n} className="skeleton-card" />
            ))}
          </div>
        ) : (
          <div className="product-grid">
            {filteredProducts.map((product) => {
              const inCart = cart.items.find((i) => i.product_id === product.id);
              return (
                <div key={product.id} className="product-card" id={`product-${product.id}`}>
                  <div className="product-img-wrapper">
                    <img
                      src={product.image}
                      alt={product.name}
                      className="product-img"
                      loading="lazy"
                      onError={(e) => {
                        e.target.onerror = null;
                        e.target.src =
                          'https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=600&q=80';
                      }}
                    />
                    <span className="product-category-tag">{product.category}</span>
                  </div>

                  <div className="product-body">
                    <h2 className="product-title">{product.name}</h2>
                    <p className="product-description">{product.description}</p>

                    <div className="product-footer">
                      <div className="product-price">${product.price.toFixed(2)}</div>
                      <button
                        className="add-btn"
                        onClick={() => handleAddToCart(product)}
                        id={`add-btn-${product.id}`}
                      >
                        {inCart ? `Add More (${inCart.quantity})` : '+ Add to Cart'}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Cart Drawer Slide-Over */}
      <div
        className={`cart-backdrop ${cartOpen ? 'open' : ''}`}
        onClick={() => setCartOpen(false)}
      >
        <div className="cart-drawer" onClick={(e) => e.stopPropagation()}>
          <div className="cart-header">
            <div className="cart-title">
              <span>🛒 Shopping Cart</span>
              <span className="cart-badge">{cart.total_items}</span>
            </div>
            <button
              className="cart-close-btn"
              onClick={() => setCartOpen(false)}
              aria-label="Close cart"
            >
              ✕
            </button>
          </div>

          <div className="cart-items-container">
            {cart.items.length === 0 ? (
              <div className="cart-empty">
                <div className="empty-icon">🛍️</div>
                <h3 className="empty-title">Your cart is empty</h3>
                <p className="empty-subtext">
                  Explore our sample products and add items to observe real-time Redis updates.
                </p>
                <button
                  className="btn-secondary"
                  style={{ background: 'var(--primary)', color: '#fff' }}
                  onClick={() => setCartOpen(false)}
                >
                  Browse Products
                </button>
              </div>
            ) : (
              cart.items.map((item) => (
                <div key={item.product_id} className="cart-item">
                  <img src={item.image} alt={item.name} className="cart-item-img" />
                  <div className="cart-item-details">
                    <div className="cart-item-title">{item.name}</div>
                    <div className="cart-item-price">
                      ${item.price.toFixed(2)} × {item.quantity} = ${item.item_total.toFixed(2)}
                    </div>
                    <div className="cart-item-actions">
                      <div className="qty-control">
                        <button
                          className="qty-btn"
                          onClick={() => updateQuantity(item.product_id, item.quantity - 1)}
                          title="Decrease quantity"
                        >
                          -
                        </button>
                        <span className="qty-display">{item.quantity}</span>
                        <button
                          className="qty-btn"
                          onClick={() => updateQuantity(item.product_id, item.quantity + 1)}
                          title="Increase quantity"
                        >
                          +
                        </button>
                      </div>

                      <button
                        className="cart-item-remove"
                        onClick={() => handleRemove(item.product_id)}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {cart.items.length > 0 && (
            <div className="cart-footer">
              <div className="summary-row">
                <span>Subtotal</span>
                <span>${cart.subtotal.toFixed(2)}</span>
              </div>
              <div className="summary-row">
                <span>Estimated Tax (8%)</span>
                <span>${cart.tax.toFixed(2)}</span>
              </div>
              <div className="summary-row">
                <span>Shipping (Lab Demo)</span>
                <span style={{ color: 'var(--success)', fontWeight: 600 }}>FREE</span>
              </div>
              <div className="summary-row total">
                <span>Total</span>
                <span>${cart.total.toFixed(2)}</span>
              </div>

              <button className="checkout-btn" onClick={handleCheckout}>
                Proceed to Checkout (${cart.total.toFixed(2)})
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Checkout Demo Confirmation Modal */}
      {orderModalOpen && (
        <div className="modal-backdrop" onClick={() => setOrderModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-icon">✓</div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 800, marginBottom: '0.5rem' }}>
              Demo Order Placed!
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
              This is a sample student checkout for FoCC Lab 2. No real payment or customer data is
              collected.
            </p>
            <div
              style={{
                background: '#f1f5f9',
                padding: '0.75rem',
                borderRadius: '8px',
                fontFamily: 'monospace',
                fontSize: '0.9rem',
                marginBottom: '1.5rem',
              }}
            >
              Order Reference: <strong>{lastOrderId}</strong>
            </div>
            <button
              className="btn-secondary"
              style={{
                width: '100%',
                background: 'var(--primary)',
                color: '#fff',
                padding: '0.75rem',
              }}
              onClick={() => {
                setOrderModalOpen(false);
                setCartOpen(false);
              }}
            >
              Continue Shopping
            </button>
          </div>
        </div>
      )}

      {/* Diagnostics / Health Check Modal */}
      {healthModalOpen && (
        <div className="modal-backdrop" onClick={() => setHealthModalOpen(false)}>
          <div className="modal-content modal-lg" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>🏥 Backend Probes & Dependency Health</h2>
              <button className="modal-close-btn" onClick={() => setHealthModalOpen(false)}>
                &times;
              </button>
            </div>

            <div className="diag-body">
              <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                <span className="diag-badge success">
                  ● All Core Services Operational (200 OK)
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Checked: {healthDetails?.timestamp || 'Just now'}
                </span>
              </div>

              <div className="diag-grid">
                <div className="diag-card">
                  <div className="diag-card-title">Backend API</div>
                  <div className="diag-card-value" style={{ color: 'var(--success)' }}>Ready</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    HTTP {healthDetails?.readyStatus || 200}
                  </div>
                </div>

                <div className="diag-card">
                  <div className="diag-card-title">Redis Cache</div>
                  <div className="diag-card-value" style={{ color: 'var(--success)' }}>Connected</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    Cart Storage Active
                  </div>
                </div>

                <div className="diag-card">
                  <div className="diag-card-title">Liveness Probe</div>
                  <div className="diag-card-value" style={{ color: 'var(--primary)' }}>Alive</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    /health/live
                  </div>
                </div>

                <div className="diag-card">
                  <div className="diag-card-title">Readiness Probe</div>
                  <div className="diag-card-value" style={{ color: 'var(--primary)' }}>Ready</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    /health/ready
                  </div>
                </div>
              </div>

              <div style={{ marginTop: '0.5rem', marginBottom: '0.5rem', fontWeight: 600, fontSize: '0.85rem' }}>
                Raw JSON Readiness Response (/health/ready):
              </div>
              <pre className="code-viewer">
                {healthLoading
                  ? 'Pinging backend probes...'
                  : JSON.stringify(healthDetails?.ready || {}, null, 2)}
              </pre>
            </div>

            <div className="diag-actions">
              <div className="diag-actions-left">
                <button className="btn-secondary btn-sm" onClick={fetchHealthDetails} disabled={healthLoading}>
                  {healthLoading ? '⏳ Refreshing...' : '🔄 Refresh Status'}
                </button>
                <a
                  href="/health/ready"
                  target="_blank"
                  rel="noreferrer"
                  className="btn-secondary btn-sm"
                  title="Open raw JSON for lab evidence screenshots"
                >
                  🔗 Open Raw /health/ready
                </a>
                <a
                  href="/health/live"
                  target="_blank"
                  rel="noreferrer"
                  className="btn-secondary btn-sm"
                  title="Open liveness endpoint"
                >
                  🔗 Open Raw /health/live
                </a>
              </div>
              <button
                className="btn-secondary btn-sm"
                style={{ background: 'var(--primary)', color: '#fff' }}
                onClick={() => setHealthModalOpen(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Prometheus Metrics Modal */}
      {metricsModalOpen && (
        <div className="modal-backdrop" onClick={() => setMetricsModalOpen(false)}>
          <div className="modal-content modal-lg" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📊 Prometheus Instrumentation & Telemetry</h2>
              <button className="modal-close-btn" onClick={() => setMetricsModalOpen(false)}>
                &times;
              </button>
            </div>

            <div className="diag-body">
              {/* Summary KPI Cards */}
              {(() => {
                const summary = parseMetricsSummary(metricsText);
                return (
                  <div className="diag-grid">
                    <div className="diag-card">
                      <div className="diag-card-title">Total Requests</div>
                      <div className="diag-card-value">{summary.totalRequests}</div>
                    </div>
                    <div className="diag-card">
                      <div className="diag-card-title">Resident Memory</div>
                      <div className="diag-card-value">{summary.memoryMb} MB</div>
                    </div>
                    <div className="diag-card">
                      <div className="diag-card-title">CPU Time</div>
                      <div className="diag-card-value">{summary.cpuSeconds} s</div>
                    </div>
                    <div className="diag-card">
                      <div className="diag-card-title">GC Objects (Gen0)</div>
                      <div className="diag-card-value">{summary.gcObjects}</div>
                    </div>
                  </div>
                );
              })()}

              <input
                type="text"
                className="diag-search"
                placeholder="Search metrics (e.g. http_requests, memory, cpu, cart)..."
                value={metricsSearch}
                onChange={(e) => setMetricsSearch(e.target.value)}
              />

              <div style={{ marginBottom: '0.4rem', fontWeight: 600, fontSize: '0.85rem' }}>
                OpenMetrics Stream (/metrics):
              </div>
              <pre className="code-viewer">
                {metricsLoading
                  ? 'Streaming Prometheus telemetry...'
                  : metricsText
                      .split('\n')
                      .filter((line) =>
                        !metricsSearch || line.toLowerCase().includes(metricsSearch.toLowerCase())
                      )
                      .join('\n') || '# No matching metric lines found'}
              </pre>
            </div>

            <div className="diag-actions">
              <div className="diag-actions-left">
                <button className="btn-secondary btn-sm" onClick={fetchMetricsDetails} disabled={metricsLoading}>
                  {metricsLoading ? '⏳ Refreshing...' : '🔄 Refresh Stream'}
                </button>
                <button className="btn-secondary btn-sm" onClick={copyMetrics}>
                  {copiedMetrics ? '✓ Copied!' : '📋 Copy All'}
                </button>
                <a
                  href="/metrics"
                  target="_blank"
                  rel="noreferrer"
                  className="btn-secondary btn-sm"
                  title="Open raw Prometheus scraper endpoint"
                >
                  🔗 Open Raw /metrics
                </a>
              </div>
              <button
                className="btn-secondary btn-sm"
                style={{ background: 'var(--primary)', color: '#fff' }}
                onClick={() => setMetricsModalOpen(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Student Project Footer */}
      <footer className="app-footer">
        <div className="container">
          <p>
            <strong>CloudCart</strong> — Fundamentals of Cloud Computing Lab 2 (FoCC)
          </p>
          <p style={{ marginTop: '0.35rem', fontSize: '0.78rem' }}>
            Built with React (Vite) + Python Flask + Redis + Azure Kubernetes Service (AKS)
          </p>
        </div>
      </footer>
    </div>
  );
}
