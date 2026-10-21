# FoCC Lab 2 — Evidence and Screenshot Submission Checklist

This document is your submission checklist. Capture the required screenshots and fill in your actual experimental observations during your lab session.

> **Student Note:** Do not fabricate numbers. Fill in the placeholders below with the real values observed on your cluster.

---

## 1. Required Screenshots Checklist

| # | Evidence Item | Command / Portal Location | Status |
|---|---------------|---------------------------|--------|
| **S1** | Local Docker Compose running all 3 containers | `docker compose ps` | [ ] Pending |
| **S2** | Local Web Application showing Product Catalog | Browser at `http://localhost:8080` | [ ] Pending |
| **S3** | Local Shopping Cart showing added items & Redis total | Browser cart drawer | [ ] Pending |
| **S4** | Backend health checks (`/health/live` & `/health/ready`) | `curl -i http://localhost:8080/health/ready` | [ ] Pending |
| **S5** | Azure Container Registry (ACR) showing pushed images | Azure Portal $\rightarrow$ Container Registries $\rightarrow$ Repositories | [ ] Pending |
| **S6** | AKS Deployments, Pods, and Services | `kubectl get all -n focc-ecommerce` | [ ] Pending |
| **S7** | AKS External IP resolving the live web store | Browser at `http://<EXTERNAL_IP>` | [ ] Pending |
| **S8** | Terminal running `load_test.py` with timestamped logs | Terminal executing load generator | [ ] Pending |
| **S9** | Live HPA scaling up replicas (`kubectl get hpa -w`) | Terminal watching HPA CPU% and replicas | [ ] Pending |
| **S10** | Pod transitions during scaling (`kubectl get pods -w`) | Terminal showing new pods starting & becoming Ready | [ ] Pending |
| **S11** | Azure Monitor / Container Insights Dashboard | Azure Portal $\rightarrow$ Insights $\rightarrow$ Performance | [ ] Pending |
| **S12** | Azure Monitor Alert Rule firing or notification email | Azure Portal $\rightarrow$ Monitor $\rightarrow$ Alerts | [ ] Pending |

---

## 2. Experimental Observations & Measurements

Fill out these tables with your actual lab data:

### Table 1: Resource Consumption (Baseline vs. Peak Load)

| Pod Name / Component | Baseline CPU | Peak Load CPU | Baseline Memory | Peak Load Memory |
|----------------------|--------------|---------------|-----------------|------------------|
| `backend-deployment` (Pod 1) | `[____] m` | `[____] m` | `[____] Mi` | `[____] Mi` |
| `backend-deployment` (Scaled) | N/A | `[____] m` | N/A | `[____] Mi` |
| `frontend-deployment` | `[____] m` | `[____] m` | `[____] Mi` | `[____] Mi` |
| `redis-deployment` | `[____] m` | `[____] m` | `[____] Mi` | `[____] Mi` |

*Commands used:*
- Baseline: `kubectl top pods -n focc-ecommerce`
- Peak: `kubectl top pods -n focc-ecommerce` during load test

---

### Table 2: HPA Scaling Milestones

| Timestamp | Observed CPU Utilization | Target CPU | Replica Count | Event / Description |
|-----------|--------------------------|------------|---------------|---------------------|
| `00:00` (Pre-test) | `[____] %` | `50%` | `1` | Normal baseline traffic |
| `00:45` (Test active) | `[____] %` | `50%` | `1 -> 2` | Threshold crossed; HPA triggers scale-up |
| `01:30` (Peak load) | `[____] %` | `50%` | `[____]` | Additional replicas provisioned |
| `03:00` (Test ended) | `[____] %` | `50%` | `[____]` | Traffic stopped; CPU drops |
| `08:00` (Cooldown) | `[____] %` | `50%` | `1` | Stabilization window passed; scaled down |

---

### Table 3: Load Test Latency & Performance Summary

*(Extract from final output of `python load-test/load_test.py`)*

- **Total Requests Dispatched:** `[________]`
- **Successful Requests (2xx):** `[________]`
- **Failed Requests (4xx/5xx):** `[________]`
- **Error Rate (%):** `[________] %`
- **Average Throughput (RPS):** `[________] req/s`
- **Minimum Latency:** `[________] ms`
- **Average Latency:** `[________] ms`
- **Median (P50) Latency:** `[________] ms`
- **P90 Latency:** `[________] ms`
- **P95 Latency:** `[________] ms`
- **Maximum Latency:** `[________] ms`

---

### Table 4: Azure Monitor Alert Trigger Log

| Metric / Alert Name | Trigger Threshold | Time Load Started | Time Alert Fired | Observed Alert Delay | Action Group Notification |
|---------------------|-------------------|-------------------|------------------|----------------------|---------------------------|
| **High CPU Alert** | $> 75\%$ for 5 min | `[HH:MM:SS]` | `[HH:MM:SS]` | `[____] min` | [ ] Email Received |
| **Pod Restarts Alert** | $> 3$ in 10 min | `[HH:MM:SS]` | `[HH:MM:SS]` | `[____] min` | [ ] Email Received |

---

### Table 5: Pod Restarts Verification

Verify if any container crashed or was restarted by the Kubernetes liveness probe:

```bash
kubectl get pods -n focc-ecommerce -o wide
```

| Pod Name | Restarts Count | Last Restart Reason | Health Check Log Snippet |
|----------|----------------|---------------------|---------------------------|
| `backend-deployment-xxxxx` | `0` (or `[__]`) | `[None / OOMKilled / LivenessProbeFailed]` | `[Paste snippet if any]` |
| `frontend-deployment-xxxxx` | `0` (or `[__]`) | `[None]` | `[Paste snippet if any]` |
| `redis-deployment-xxxxx` | `0` (or `[__]`) | `[None]` | `[Paste snippet if any]` |
