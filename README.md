# Mini E-Commerce Store — Fundamentals of Cloud Computing (FoCC) Lab 2

A production-ready, cloud-native microservices e-commerce application designed for students and engineers learning cloud infrastructure, containerization, and orchestration.

![FoCC Lab 2 Architecture](https://img.shields.io/badge/Architecture-Cloud--Native%20Microservices-blue)
![Frontend](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite%20%2B%20Nginx-61DAFB)
![Backend](https://img.shields.io/badge/Backend-Python%20Flask%20%2B%20Gunicorn-3776AB)
![Cache](https://img.shields.io/badge/Cache-Redis%207-DC382D)
![Orchestration](https://img.shields.io/badge/Kubernetes-AKS%20%2B%20HPA-326CE5)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Folder Structure](#2-folder-structure)
3. [Technology Choices & Architecture Decisions](#3-technology-choices--architecture-decisions)
4. [Local Prerequisites](#4-local-prerequisites)
5. [Step-by-Step Order of Operations](#5-step-by-step-order-of-operations)
6. [Local Testing with Docker Compose](#6-local-testing-with-docker-compose)
7. [API Endpoint Guide & `curl` Examples](#7-api-endpoint-guide--curl-examples)
8. [Azure Container Registry (ACR) Preparation](#8-azure-container-registry-acr-preparation)
9. [Azure Kubernetes Service (AKS) Deployment](#9-azure-kubernetes-service-aks-deployment)
10. [Horizontal Pod Autoscaler (HPA) Verification](#10-horizontal-pod-autoscaler-hpa-verification)
11. [Azure Monitor, Container Insights & Alerts](#11-azure-monitor-container-insights--alerts)
12. [Liveness vs. Readiness Probes & Debugging Guide](#12-liveness-vs-readiness-probes--debugging-guide)
13. [Load Testing with Automated Python Tool](#13-load-testing-with-automated-python-tool)
14. [Troubleshooting Common Cloud Issues](#14-troubleshooting-common-cloud-issues)
15. [Resource Cleanup (Avoid Unwanted Azure Charges)](#15-resource-cleanup-avoid-unwanted-azure-charges)
16. [Lab Submission Checklist](#16-lab-submission-checklist)

---

## 1. Architecture Overview

```
                      +------------------------------------------+
                      |         Student Browser / Client         |
                      +------------------------------------------+
                                           |
                              HTTP Port 8080 (Compose)
                              HTTP Port 80 (AKS LoadBalancer)
                                           v
+----------------------------------------------------------------------------------+
| Frontend Pod / Container (Nginx Alpine + React SPA)                              |
| - Serves static HTML/JS/CSS assets built with Vite                               |
| - Reverse proxies /api/*, /health/*, and /metrics to the Backend                 |
+----------------------------------------------------------------------------------+
                                           |
                                Internal HTTP (Port 5000)
                                           v
+----------------------------------------------------------------------------------+
| Backend Pod / Container (Python 3.11 Slim + Gunicorn + Flask)                    |
| - Product catalog endpoints (/api/products)                                      |
| - Cart calculation and Redis state manipulation (/api/cart)                      |
| - Liveness (/health/live) & Readiness (/health/ready)                            |
| - Prometheus metrics stream (/metrics)                                           |
| - Safe, controlled CPU burn endpoint (/api/test-load)                            |
+----------------------------------------------------------------------------------+
                                           |
                              Internal TCP (Port 6379)
                                           v
+----------------------------------------------------------------------------------+
| Redis Pod / Container (Redis 7 Alpine)                                           |
| - In-memory key-value & hash store for active demo carts                         |
| - Non-exposed, internal service only                                             |
+----------------------------------------------------------------------------------+
```

---

## 2. Folder Structure

```
mini-ecommerce-focc-lab2/
├── .gitignore                      # Git exclusion rules (secrets, node_modules, pycache)
├── docker-compose.yml              # Multi-container local orchestration
├── README.md                       # Complete guide, cloud documentation, and troubleshooting
├── backend/
│   ├── app.py                      # Flask REST API, Redis integration, Probes, Prometheus
│   ├── requirements.txt            # Pinned Python dependencies
│   ├── Dockerfile                  # Lightweight Python 3.11-slim, non-root user, Gunicorn
│   └── .dockerignore               # Backend build context exclusions
├── frontend/
│   ├── package.json                # React 18, Vite dependencies
│   ├── vite.config.js              # Vite build setup & dev proxy
│   ├── index.html                  # Responsive HTML5 entry point with Google Fonts
│   ├── nginx.conf                  # Production Nginx reverse-proxy & SPA config
│   ├── Dockerfile                  # Multi-stage build (Node builder -> Nginx runtime)
│   ├── .dockerignore               # Frontend build context exclusions
│   └── src/
│       ├── main.jsx                # React DOM root render
│       ├── App.jsx                 # Catalog, cart drawer, lab controls & states
│       └── index.css               # Design system tokens, responsive layout, animations
├── k8s/
│   ├── namespace.yaml              # Dedicated 'focc-ecommerce' namespace
│   ├── configmap.yaml              # Backend environment variables
│   ├── redis.yaml                  # Redis Deployment & internal ClusterIP Service
│   ├── deployment.yaml             # Frontend & Backend Deployments (Requests/Limits/Probes)
│   ├── service.yaml                # Frontend LoadBalancer & Backend ClusterIP
│   └── hpa.yaml                    # HorizontalPodAutoscaler (50% CPU target, 1-5 replicas)
├── load-test/
│   ├── load_test.py                # Concurrent Python load generator (Standard Library)
│   └── README.md                   # Staged test execution & observation guide
└── evidence/
    └── README.md                   # Screenshot checklist & measurement observation tables
```

---

## 3. Technology Choices & Architecture Decisions

| Component | Choice | Educational & Technical Rationale |
|-----------|--------|-----------------------------------|
| **Frontend** | React 18 + Vite | Fast compilation, modern hooks for clean cart state, easy containerization. |
| **Web Server** | Nginx Alpine | Serves static assets at 10x lower memory overhead than Node.js runtime (~15MB RAM). Acts as a reverse proxy so the React client calls relative URLs (`/api/...`), avoiding Cross-Origin (CORS) problems. |
| **Backend** | Python Flask + Gunicorn | Straightforward syntax suitable for data science students, multi-threaded Gunicorn WSGI server handles concurrent requests without deadlocks. |
| **Data Store** | Redis 7 Alpine | Fast in-memory hash store for carts; decoupled from the application runtime to teach stateful vs. stateless architecture. |
| **Orchestration** | AKS + HPA | Real-world cloud standard. Uses native Kubernetes resource metrics (`cpu`) to demonstrate elasticity under load. |

---

## 4. Local Prerequisites

Before starting, ensure you have:
1. **Docker Desktop** installed and running on your workstation.
2. **Docker Compose v2+** (included with modern Docker Desktop).
3. **Python 3.10+** (for running the load test script locally).
4. **Azure CLI (`az`)** (for ACR and AKS steps later).
5. **`kubectl`** CLI (for managing Kubernetes clusters).

---

## 5. Step-by-Step Order of Operations

To ensure smooth lab execution, always follow this order:
```
[Step 1] Build & Run locally with Docker Compose
   └── Verify Catalog, Cart, Health endpoints, and Lab Testing Panel
[Step 2] Tag & Push container images to Azure Container Registry (ACR)
   └── Authenticate via Azure CLI and verify images exist in registry
[Step 3] Deploy to Azure Kubernetes Service (AKS)
   └── Apply Namespace -> ConfigMap -> Redis -> Deployments -> Services -> HPA
[Step 4] Validate Probes and Metrics Server
   └── Verify 'kubectl top pods' and 'kubectl get hpa'
[Step 5] Configure Azure Monitor & Alert Rules in Azure Portal
   └── Set CPU Alert (>75%) and Pod Restarts Alert (>3)
[Step 6] Execute Controlled Load Test
   └── Run load_test.py, record HPA scaling, capture screenshots
[Step 7] Clean Up Azure Resources
   └── Delete namespace or AKS cluster to prevent unexpected cloud billing
```

---

## 6. Local Testing with Docker Compose

### 6.1 Start the Application

Open PowerShell or terminal in the repository root and execute:

```bash
docker compose up --build
```

Docker Compose will:
1. Create a user-defined bridge network `ecommerce-net`.
2. Launch the `redis` container with persistent data storage and a healthcheck.
3. Build the `backend` container from `./backend/Dockerfile` and start Gunicorn once Redis is healthy.
4. Build the `frontend` container using the multi-stage `./frontend/Dockerfile` and launch Nginx.

### 6.2 Verify Running Services

In another terminal, check container health:

```bash
docker compose ps
```

*Expected output:*
```
NAME                 IMAGE               STATUS                    PORTS
ecommerce-redis      redis:7-alpine      Up (healthy)              6379/tcp
ecommerce-backend    backend-image       Up (healthy)              0.0.0.0:5000->5000/tcp
ecommerce-frontend   frontend-image      Up (healthy)              0.0.0.0:8080->80/tcp
```

### 6.3 Open the Web Store

Navigate your browser to:
[http://localhost:8080](http://localhost:8080)

You should observe:
- The **CloudCart** interface with 8 sample tech and study products.
- A green **Backend Ready** pill in the navigation bar.
- Add products to the cart, adjust quantities (+ / -), and delete items.
- Inspect the **⚡ Lab Testing Controls** toolbar at the top:
  - Click **🔥 Test CPU Load** to trigger a controlled 2-second backend CPU burst.
  - Click **Health Check** to verify live JSON dependency status.
  - Click **Prometheus Metrics** to view raw Prometheus metrics.

### 6.4 Stopping Docker Compose

```bash
# Stop containers gracefully
docker compose down

# Stop containers and remove persistent volumes (fresh start)
docker compose down -v
```

---

## 7. API Endpoint Guide & `curl` Examples

You can test all REST endpoints directly using `curl` or your browser:

### 1. Product Catalog (`GET /api/products`)
```bash
curl -s http://localhost:8080/api/products
```
*Sample Response (200 OK):*
```json
{
  "count": 8,
  "products": [
    {
      "id": "prod-1",
      "name": "Cloud Architecture Blueprint Poster",
      "category": "Accessories",
      "price": 19.99,
      "description": "High-res glossy poster covering distributed systems...",
      "image": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?..."
    }
  ]
}
```

### 2. View Current Demo Cart (`GET /api/cart`)
```bash
curl -s http://localhost:8080/api/cart
```
*Sample Response (200 OK):*
```json
{
  "items": [],
  "shipping": 0.0,
  "subtotal": 0.0,
  "tax": 0.0,
  "total": 0.0,
  "total_items": 0
}
```

### 3. Add or Update Product in Cart (`POST /api/cart`)
```bash
curl -s -X POST http://localhost:8080/api/cart \
  -H "Content-Type: application/json" \
  -d '{"product_id": "prod-1", "quantity": 2}'
```
*Sample Response (200 OK):*
```json
{
  "message": "Cart updated successfully.",
  "cart": {
    "items": [
      {
        "product_id": "prod-1",
        "name": "Cloud Architecture Blueprint Poster",
        "category": "Accessories",
        "price": 19.99,
        "quantity": 2,
        "item_total": 39.98
      }
    ],
    "subtotal": 39.98,
    "tax": 3.2,
    "shipping": 0.0,
    "total": 43.18,
    "total_items": 2
  }
}
```

### 4. Remove Item from Cart (`DELETE /api/cart/<product_id>`)
```bash
curl -s -X DELETE http://localhost:8080/api/cart/prod-1
```

### 5. Liveness Probe (`GET /health/live`)
Verifies that the backend process is running:
```bash
curl -i http://localhost:8080/health/live
```
*Sample Response (200 OK):*
```json
{
  "service": "mini-ecommerce-backend",
  "status": "alive",
  "timestamp": "2026-10-21T17:15:00.000000Z"
}
```

### 6. Readiness Probe (`GET /health/ready`)
Verifies that Redis is connected and accepting commands:
```bash
curl -i http://localhost:8080/health/ready
```
*Sample Response (200 OK):*
```json
{
  "dependencies": {
    "redis": "ok"
  },
  "redis": "connected",
  "status": "ready",
  "timestamp": "2026-10-21T17:15:00.000000Z"
}
```
*(If Redis is stopped or unreachable, this endpoint returns `503 Service Unavailable` with `status: not_ready`.)*

### 7. Prometheus Metrics (`GET /metrics`)
```bash
curl -s http://localhost:8080/metrics | head -n 25
```
*Exposes:*
- `http_requests_total{endpoint="/api/products",method="GET",status="200"}`
- `http_request_duration_seconds_bucket{endpoint="/api/products",le="0.1"}`
- `http_request_errors_total`

### 8. Controlled CPU Load (`GET /api/test-load?duration=2`)
Runs a safe CPU-bound loop for the requested duration (limited to $\le 5$ seconds):
```bash
curl -s "http://localhost:8080/api/test-load?duration=2"
```
*Sample Response (200 OK):*
```json
{
  "actual_duration_seconds": 2.0014,
  "iterations": 184523,
  "message": "Controlled CPU load test executed successfully.",
  "requested_duration_seconds": 2.0,
  "status": "completed"
}
```

---

## 8. Azure Container Registry (ACR) Preparation

When preparing to deploy on Azure, build your images and push them to your ACR repository.

> **Security Note:** Never put registry credentials or secrets in Git. Always authenticate via the Azure CLI.

### Step 1: Set Variables in PowerShell or Bash
```bash
# In Bash:
export ACR_NAME="myfoccacr123"          # Replace with your actual ACR name
export ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
export VERSION="v1.0.0"

# In PowerShell:
$ACR_NAME="myfoccacr123"
$ACR_LOGIN_SERVER="$ACR_NAME.azurecr.io"
$VERSION="v1.0.0"
```

### Step 2: Log in to ACR
```bash
az acr login --name $ACR_NAME
```
*(Confirms `Login Succeeded` without exposing passwords.)*

### Step 3: Build and Tag Images
```bash
# Build Backend Image
docker build -t ${ACR_LOGIN_SERVER}/focc-backend:${VERSION} ./backend

# Build Frontend Image
docker build -t ${ACR_LOGIN_SERVER}/focc-frontend:${VERSION} ./frontend
```

### Step 4: Push Images to ACR
```bash
docker push ${ACR_LOGIN_SERVER}/focc-backend:${VERSION}
docker push ${ACR_LOGIN_SERVER}/focc-frontend:${VERSION}
```

### Step 5: Verify Images in Registry
```bash
az acr repository list --name $ACR_NAME --output table
az acr repository show-tags --name $ACR_NAME --repository focc-backend --output table
az acr repository show-tags --name $ACR_NAME --repository focc-frontend --output table
```

---

## 9. Azure Kubernetes Service (AKS) Deployment

### 9.1 Connect `kubectl` to your AKS Cluster
```bash
az aks get-credentials --resource-group <MY_RESOURCE_GROUP> --name <MY_AKS_CLUSTER>
```

### 9.2 Attach ACR to your AKS Cluster
If not already attached during creation, authorize AKS to pull images from ACR:
```bash
az aks update -n <MY_AKS_CLUSTER> -g <MY_RESOURCE_GROUP> --attach-acr $ACR_NAME
```

### 9.3 Update Image Placeholders in `k8s/deployment.yaml`
Open [`k8s/deployment.yaml`](file:///c:/Users/asus/OneDrive/文档/mini-ecommerce-focc-lab2/k8s/deployment.yaml) and replace `<ACR_NAME>` with your ACR name:
- Line 31: `<ACR_NAME>.azurecr.io/focc-backend:v1.0.0` $\rightarrow$ `myfoccacr123.azurecr.io/focc-backend:v1.0.0`
- Line 83: `<ACR_NAME>.azurecr.io/focc-frontend:v1.0.0` $\rightarrow$ `myfoccacr123.azurecr.io/focc-frontend:v1.0.0`

### 9.4 Apply Manifests in Sequence
```bash
# 1. Create Namespace
kubectl apply -f k8s/namespace.yaml

# 2. Apply ConfigMap
kubectl apply -f k8s/configmap.yaml

# 3. Deploy Redis Cache
kubectl apply -f k8s/redis.yaml

# 4. Deploy Backend and Frontend Workloads
kubectl apply -f k8s/deployment.yaml

# 5. Create Services (Internal Backend ClusterIP & Frontend LoadBalancer)
kubectl apply -f k8s/service.yaml

# 6. Apply HorizontalPodAutoscaler
kubectl apply -f k8s/hpa.yaml
```

### 9.5 Validation Commands

Verify that all resources have rolled out successfully:

```bash
# Check all pods, deployments, and services in the namespace
kubectl get all -n focc-ecommerce

# Watch external IP assignment for the frontend
kubectl get svc frontend -n focc-ecommerce -w
```

Once `EXTERNAL-IP` changes from `<pending>` to a public IP (e.g. `20.55.120.40`), open:
`http://<EXTERNAL-IP>` in your browser!

```bash
# Check pod resource utilization
kubectl top pods -n focc-ecommerce

# Check recent events (vital for troubleshooting probe or scheduling issues)
kubectl get events -n focc-ecommerce --sort-by='.metadata.creationTimestamp'

# View Backend Gunicorn logs
kubectl logs -l component=backend -n focc-ecommerce --tail=50
```

---

## 10. Horizontal Pod Autoscaler (HPA) Verification

### 10.1 Why CPU Requests are Required for HPA
The HPA calculates CPU utilization as:
$$\text{Current Utilization \%} = \frac{\text{Current Pod CPU Usage}}{\text{Requested Pod CPU}} \times 100\%$$

In [`k8s/deployment.yaml`](file:///c:/Users/asus/OneDrive/文档/mini-ecommerce-focc-lab2/k8s/deployment.yaml), we defined:
```yaml
resources:
  requests:
    cpu: 100m       # 0.1 CPU core baseline
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```
If `requests.cpu` were omitted, Kubernetes would not have a denominator for the equation. As a result, `kubectl get hpa` would display:
`TARGETS: <unknown>/50%` and the autoscaler would **never** scale!

### 10.2 Verify Metrics Server
Ensure the Kubernetes Metrics Server is operational on your cluster:
```bash
kubectl get deployment metrics-server -n kube-system
kubectl top nodes
kubectl top pods -n focc-ecommerce
```

### 10.3 Check Initial HPA State
```bash
kubectl get hpa backend-hpa -n focc-ecommerce
```
*Expected initial output:*
```
NAME          REFERENCE                       TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
backend-hpa   Deployment/backend-deployment   2%/50%    1         5         1          2m
```

---

## 11. Azure Monitor, Container Insights & Alerts

### 11.1 Enabling Container Insights
1. Open the **Azure Portal** ([portal.azure.com](https://portal.azure.com)).
2. Navigate to your **Kubernetes cluster** (AKS).
3. Under the **Monitoring** section in the left sidebar, click **Insights**.
4. If not already enabled, click **Enable Container Insights** and associate it with a Log Analytics workspace.

### 11.2 Creating an Azure Dashboard
Create a monitoring dashboard to display key operational metrics:
1. Search for **Dashboard** in the Azure Portal search bar $\rightarrow$ **+ Create** $\rightarrow$ **Custom Dashboard**.
2. Add the following tiles:
   - **Backend CPU Utilization:** Metric: `CPU Usage Millicores` or `Container CPU percentage`.
   - **Backend Memory Usage:** Metric: `Memory Working Set Percentage`.
   - **Pod Replica Count:** Metric: `Pod Count` filtered by namespace `focc-ecommerce` and workload `backend-deployment`.
   - **Pod Restarts:** Kusto Log query from Container Insights:
     ```kusto
     KubePodInventory
     | where Namespace == "focc-ecommerce"
     | summarize Restarts = sum(PodRestartCount) by PodUid, Name, bin(TimeGenerated, 5m)
     | render timechart
     ```

### 11.3 Prometheus Metrics (Request Count & P95 Latency)
> **Cloud Engineering Note:** Standard Container Insights monitors infrastructure metrics (CPU, RAM, disk, network) automatically. Application-level metrics (such as HTTP request count and P95 latency exposed at `/metrics`) require **Azure Monitor Managed Service for Prometheus** or configuring the Container Insights Prometheus scraping ConfigMap (`container-azm-ms-agentconfig`). They do not appear automatically without Prometheus scraping configured.

To scrape the application metrics:
- Ensure Azure Monitor Managed Prometheus is enabled on your AKS cluster, OR
- Review the `/metrics` endpoint directly in the browser or terminal using:
  ```bash
  curl -s http://<EXTERNAL-IP>/metrics
  ```

### 11.4 Configuring Alert 1: High CPU Utilization (>75% for 5 min)
1. In your AKS cluster page, go to **Monitoring** $\rightarrow$ **Alerts** $\rightarrow$ **+ Create** $\rightarrow$ **Alert rule**.
2. **Signal name:** Select `CPU Percentage` or `Average CPU Utilization`.
3. **Condition:**
   - Threshold: **Static**
   - Operator: **Greater than**
   - Threshold value: **75%**
   - Unit: `Percentage`
   - Aggregation granularity (Period): **5 minutes**
   - Frequency of evaluation: **1 minute**
4. **Actions:**
   - Click **Add action groups** $\rightarrow$ **Create action group**.
   - Action group name: `focc-lab2-alerts`.
   - Notification type: `Email/SMS/Push/Voice` $\rightarrow$ Enter your student email address.
5. **Details:**
   - Severity: **2 - Warning**
   - Alert rule name: `Alert-Backend-HighCPU-75pct`.
6. Click **Review + Create**.

### 11.5 Configuring Alert 2: Excessive Pod Restarts (>3 in 10 min)
1. Go to **Alerts** $\rightarrow$ **+ Create** $\rightarrow$ **Alert rule**.
2. **Signal type:** Select **Log** (Log Analytics query).
3. **Search query:**
   ```kusto
   KubePodInventory
   | where Namespace == "focc-ecommerce"
   | where PodStatus in ("CrashLoopBackOff", "Failed", "Error") or PodRestartCount > 0
   | summarize TotalRestarts = max(PodRestartCount) by PodUid, Name
   | where TotalRestarts > 3
   ```
4. **Condition:**
   - Measurement: Table rows
   - Operator: **Greater than**
   - Threshold value: **0**
   - Period: **10 minutes**
   - Frequency: **5 minutes**
5. **Actions:** Attach the same `focc-lab2-alerts` Action Group.
6. **Details:**
   - Severity: **1 - Error**
   - Alert rule name: `Alert-Pod-Restarts-Exceeded`.
7. Click **Review + Create**.

---

## 12. Liveness vs. Readiness Probes & Debugging Guide

### 12.1 Concept Comparison

| Aspect | Liveness Probe (`/health/live`) | Readiness Probe (`/health/ready`) |
|--------|---------------------------------|-----------------------------------|
| **Purpose** | Detects if the process has deadlocked or crashed. | Detects if the pod is initialized and dependencies (Redis) are ready to handle requests. |
| **Kubernetes Action upon Failure** | **Kills and restarts the container.** | **Removes the pod IP from the Service Endpoints.** Incoming user traffic is routed only to other ready pods. Container is NOT restarted. |
| **Critical Design Rule** | **Never check downstream dependencies (like Redis) in a liveness probe.** If Redis goes down, restarting the backend container will not fix Redis—it only causes a restart storm (CrashLoopBackOff) across all pods! | **Always check external dependencies (Redis, database) in readiness probes.** If Redis goes down, pods stop taking traffic until Redis recovers. |

### 12.2 How to Investigate a Slow Application
If requests to your cluster are slow or timing out:
1. **Check Pod Status and Restarts:**
   ```bash
   kubectl get pods -n focc-ecommerce -o wide
   ```
   *Look for non-zero `RESTARTS` or `CrashLoopBackOff`.*
2. **Check Current CPU/Memory Throttle:**
   ```bash
   kubectl top pods -n focc-ecommerce
   ```
   *If CPU usage is near `500m` (the limit), the Linux kernel is throttling CPU time slices.*
3. **Inspect Kubernetes Events for Node/Pod Pressure:**
   ```bash
   kubectl describe pod <POD_NAME> -n focc-ecommerce
   ```
   *Check for `OOMKilled` (Out of Memory) or failed probe messages.*
4. **Inspect Application Logs:**
   ```bash
   kubectl logs <POD_NAME> -n focc-ecommerce --previous
   ```
5. **Verify Redis Response Times:**
   ```bash
   kubectl exec -it <REDIS_POD_NAME> -n focc-ecommerce -- redis-cli --latency
   ```

---

## 13. Load Testing with Automated Python Tool

The [`load-test/load_test.py`](file:///c:/Users/asus/OneDrive/文档/mini-ecommerce-focc-lab2/load-test/load_test.py) script sends concurrent requests to the product catalog and the controlled CPU load endpoint.

### Step 1: Open 3 Terminal Windows

- **Terminal 1 (Pod Watcher):**
  ```bash
  kubectl get pods -n focc-ecommerce -w
  ```
- **Terminal 2 (HPA Watcher):**
  ```bash
  kubectl get hpa backend-hpa -n focc-ecommerce -w
  ```
- **Terminal 3 (Load Test Execution):**

### Step 2: Run the 3-Minute Load Test
```bash
python load-test/load_test.py --url http://<EXTERNAL-IP> --concurrency 6 --duration 180
```

### Step 3: Observe the Dynamics
- Within 30 seconds, HPA CPU utilization will climb past 50%.
- In Terminal 2, you will see `REPLICAS` increase: `1` $\rightarrow$ `2` $\rightarrow$ `3` (up to `5`).
- In Terminal 1, new backend pods transition from `ContainerCreating` $\rightarrow$ `Running` $\rightarrow$ `1/1 Ready`.
- Once the load test finishes at 180s, the summary report prints:
  - Total requests, Error Rate, Avg Latency, and P95 Latency.
- In Terminal 2, observe that HPA waits for the **stabilization window** (5 minutes) before scaling replicas back down to 1.

---

## 14. Troubleshooting Common Cloud Issues

### Issue 1: HPA shows `<unknown>/50%`
- **Cause 1:** Pods lack `resources.requests.cpu`. Check [`k8s/deployment.yaml`](file:///c:/Users/asus/OneDrive/文档/mini-ecommerce-focc-lab2/k8s/deployment.yaml).
- **Cause 2:** Metrics Server is not installed or still gathering the first sample (wait 30-60 seconds).
- **Fix:** Run `kubectl top pods -n focc-ecommerce` to confirm metrics collection.

### Issue 2: Pods stuck in `ImagePullBackOff` or `ErrImagePull`
- **Cause:** AKS does not have permission to pull from ACR or image name is mistyped.
- **Fix:**
  ```bash
  az aks update -n <CLUSTER_NAME> -g <RESOURCE_GROUP> --attach-acr <ACR_NAME>
  ```
  Verify the image tag matches what you pushed using `az acr repository show-tags`.

### Issue 3: Pods show `CrashLoopBackOff`
- **Cause:** Application error on startup.
- **Fix:**
  ```bash
  kubectl logs -n focc-ecommerce <POD_NAME>
  kubectl describe pod -n focc-ecommerce <POD_NAME>
  ```

### Issue 4: Frontend LoadBalancer IP remains `<pending>`
- **Cause:** Azure Public IP quota exceeded or running on a local cluster without a cloud load balancer.
- **Alternative:** Use port-forwarding for testing:
  ```bash
  kubectl port-forward svc/frontend 8080:80 -n focc-ecommerce
  ```
  Then access at `http://localhost:8080`.

---

## 15. Resource Cleanup (Avoid Unwanted Azure Charges)

To ensure you do not incur unwanted cloud charges after completing the lab:

```bash
# 1. Delete all lab Kubernetes resources in the namespace
kubectl delete namespace focc-ecommerce

# 2. Delete the AKS cluster and resource group when completely finished
az aks delete --name <MY_AKS_CLUSTER> --resource-group <MY_RESOURCE_GROUP> --yes --no-wait
az group delete --name <MY_RESOURCE_GROUP> --yes --no-wait
```

---

## 16. Lab Submission Checklist

Refer to [`evidence/README.md`](file:///c:/Users/asus/OneDrive/文档/mini-ecommerce-focc-lab2/evidence/README.md) for the exact screenshot checklist and table placeholders:

- [ ] Screenshot 1: Local Docker Compose running (`docker compose ps`).
- [ ] Screenshot 2: Local Web UI with product catalog and Redis shopping cart.
- [ ] Screenshot 3: Backend health check responses (`/health/live` & `/health/ready`).
- [ ] Screenshot 4: ACR repository showing pushed `focc-backend` and `focc-frontend` images.
- [ ] Screenshot 5: AKS pods, deployments, and services running (`kubectl get all -n focc-ecommerce`).
- [ ] Screenshot 6: Terminal output of `load_test.py` with timestamped progression and P95 latency.
- [ ] Screenshot 7: HPA scaling up replicas (`kubectl get hpa -w`).
- [ ] Screenshot 8: Pod transitions from 1 to multiple replicas (`kubectl get pods -w`).
- [ ] Screenshot 9: Azure Monitor Container Insights dashboard or Alert firing.
- [ ] Completed observations tables in [`evidence/README.md`](file:///c:/Users/asus/OneDrive/文档/mini-ecommerce-focc-lab2/evidence/README.md).
