# Load Testing Guide — FoCC Lab 2

This directory contains the automated load-testing tool for the Mini E-commerce Store. It tests backend scalability, validates the Kubernetes Horizontal Pod Autoscaler (HPA), and triggers configured Azure Monitor alerts.

---

## 1. Overview & Dynamics of HPA Scaling

Before running the load test, it is essential to understand **how Kubernetes and the HPA make autoscaling decisions**:

- **Autoscaling is NOT instantaneous:** 
  1. The **Metrics Server** samples pod CPU usage periodically (typically every 15–30 seconds).
  2. The **HPA controller** evaluates the metrics against the target (`50%` CPU utilization) every 15 seconds.
  3. When an autoscaling threshold is exceeded, the HPA increases the desired replica count.
  4. The **Kubernetes Scheduler** assigns new pods to cluster worker nodes.
  5. The container runtime pulls images (if needed) and starts the container.
  6. The **Startup and Readiness probes** verify the pod is healthy before routing incoming traffic to it.
- **Why CPU Requests are Mandatory:**
  The HPA calculates CPU utilization as:
  $$\text{Utilization \%} = \frac{\text{Current CPU usage (cores)}}{\text{Requested CPU (cores)}} \times 100\%$$
  Our backend deployment requests `100m` ($0.1$ CPU core). When a pod uses $0.05$ cores, utilization is $50\%$. If CPU requests are omitted from the manifest, the HPA cannot compute a percentage and reports `<unknown>/50%`, completely breaking autoscaling!

---

## 2. Staged Load Test Procedure

Follow this staged procedure step-by-step for your lab report:

### Stage 1: Verify Application Health
Confirm all pods are in `Running` and `Ready` states:
```bash
kubectl get pods -n focc-ecommerce
curl http://<FRONTEND_IP>/health/ready
```

### Stage 2: Record Pre-Test Baseline
Open a dedicated terminal window and run:
```bash
# Terminal 1: Watch pods and replica counts
kubectl get pods -n focc-ecommerce -w

# Terminal 2: Watch HPA CPU utilization and replicas
kubectl get hpa backend-hpa -n focc-ecommerce -w
```
Also check resource consumption:
```bash
kubectl top pods -n focc-ecommerce
```
*Note down baseline metrics: Replicas = 1, CPU = 2m-5m (2-5%), Memory = ~45Mi.*

---

### Stage 3: Execute the Load Test
In **Terminal 3**, run the load generator for 3 minutes (180 seconds):

```bash
# Against local Docker Compose:
python load-test/load_test.py --url http://localhost:8080 --concurrency 6 --duration 180

# Against Azure AKS cluster:
python load-test/load_test.py --url http://<EXTERNAL-LOADBALANCER-IP> --concurrency 6 --duration 180
```

### Options:
- `--url`: Base URL of the frontend (or backend).
- `--concurrency`: Number of concurrent workers (default: `6`).
- `--duration`: Total runtime in seconds (default: `180` = 3 minutes).
- `--cpu-ratio`: Fraction of calls sent to `/api/test-load` vs catalog browsing (default: `0.6`).
- `--load-duration`: Duration of CPU burn per call (default: `1.5` seconds, max allowed: `5.0`).

To safely stop the test early at any time, press **Ctrl+C**. The script will safely terminate worker threads and print the summary statistics.

---

### Stage 4: Observe HPA Scaling & Pod Readiness
While the test runs, observe **Terminal 2**:
1. Within 30–60 seconds, CPU utilization jumps above 50% (e.g., `120%/50%`).
2. Desired replicas increases from `1` $\rightarrow$ `2` $\rightarrow$ `3` (up to `5`).
3. In **Terminal 1**, observe new pods transitioning: `Pending` $\rightarrow$ `ContainerCreating` $\rightarrow$ `Running` $\rightarrow$ `1/1 Ready`.
4. As new pods become ready, average CPU utilization stabilizes back towards the 50% target.

---

### Stage 5: Observe Azure Monitor Alerts
- If sustained CPU exceeds 75% for 5 minutes, verify that your Azure Monitor Action Group sends an alert email/notification.
- Check the Azure Portal **Alerts** page under your AKS cluster.

---

### Stage 6: Post-Test Cooldown (Scale-Down)
When the load test finishes:
- CPU utilization drops back to baseline (~2%).
- Observe that HPA **does not scale down immediately**. It observes a **stabilization window** (default 300 seconds / 5 minutes) configured in `k8s/hpa.yaml` to prevent flapping (rapid scale-up / scale-down cycles).
- After the stabilization period, replicas scale back to `1`.
