# Mini E-Commerce (CloudCart) - FoCC Lab 2

A small microservices store used to practise containers, Kubernetes autoscaling and cloud monitoring on Azure.

- **frontend** - React (Vite) served by Nginx
- **backend** - Flask REST API (`/api/products`, `/health/live`, `/health/ready`, `/metrics`)
- **redis** - cache, checked by the readiness probe

```
.
├── backend/            Flask API + Dockerfile
├── frontend/           React app + multi-stage Dockerfile + nginx.conf
├── k8s/                namespace, configmap, deployment, service, hpa, redis manifests
├── load-test/          load_test.py
├── docker-compose.yml  local run (shared bridge network)
└── README.md
```

## Prerequisites
Docker Desktop, Azure CLI, kubectl, Python 3.10+, an Azure subscription (region must be allowed by your policy, e.g. `koreacentral`).

```bash
export RG=rg-focc-lab2
export ACR=<your-acr-name>
export AKS=aks-focc-lab2
export REGION=koreacentral
```

---

## Step 1 - Containerize with Docker

Run locally:
```bash
docker compose build
docker compose up -d
docker compose ps          # frontend, backend, redis on the same bridge network
```
Build, tag and push to ACR (ACR Tasks are blocked on student plans, so build locally):
```bash
az group create -n $RG -l $REGION
az acr create -g $RG -n $ACR --sku Basic -l $REGION
az acr login -n $ACR

docker tag mini-ecommerce-focc-lab2-backend:latest  $ACR.azurecr.io/mini-ecommerce-backend:v1
docker tag mini-ecommerce-focc-lab2-frontend:latest $ACR.azurecr.io/mini-ecommerce-frontend:v1
docker push $ACR.azurecr.io/mini-ecommerce-backend:v1
docker push $ACR.azurecr.io/mini-ecommerce-frontend:v1
az acr repository list -n $ACR -o table
```

## Step 2 - Deploy to AKS and scale with HPA

```bash
az provider register -n Microsoft.ContainerService
az provider register -n Microsoft.OperationalInsights
az provider register -n Microsoft.Insights

az aks create -g $RG -n $AKS -l $REGION --node-count 1 \
  --node-vm-size Standard_B2s_v2 --attach-acr $ACR --generate-ssh-keys --tier free
az aks get-credentials -g $RG -n $AKS --overwrite-existing
kubectl get nodes

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
kubectl get pods,svc,hpa -n focc-ecommerce
kubectl describe pod -l component=backend -n focc-ecommerce | grep -iE "Image:|Requests|cpu:|memory:|Liveness|Readiness|Startup"
curl -s http://<FRONTEND-EXTERNAL-IP>/health/ready
```

Backend resources: requests `100m` CPU / `128Mi`, HPA scales 1-5 replicas above 50% CPU.

### `k8s/deployment.yaml` - Prometheus annotations (backend)
Add the three `prometheus.io/*` annotations under the **backend** pod template, so the repo matches what is deployed:

```yaml
  template:
    metadata:
      labels:
        app: mini-ecommerce
        component: backend
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "5000"
        prometheus.io/path: "/metrics"
```

---

## Step 3 - Cloud metrics monitoring (Container Insights, dashboard, alerts)

### 3.1 Log Analytics workspace + Container Insights
Free accounts have a 500 MB/day ingestion limit, so collect only what is needed (one namespace, 1-minute interval, no container logs).

```bash
az monitor log-analytics workspace create -g $RG -n law-focc-lab2 -l $REGION
WS=$(az monitor log-analytics workspace show -g $RG -n law-focc-lab2 --query id -o tsv)
echo $WS    # must print a long /subscriptions/... path

# optional safety net: stop ingestion for the day at 0.5 GB
az monitor log-analytics workspace update -g $RG -n law-focc-lab2 --quota 0.5

cat > dcr-settings.json <<'JSON'
{
  "interval": "1m",
  "namespaceFilteringMode": "Include",
  "namespaces": ["focc-ecommerce"],
  "enableContainerLogV2": false,
  "streams": ["Microsoft-InsightsMetrics", "Microsoft-KubePodInventory", "Microsoft-KubeEvents"]
}
JSON

az aks enable-addons -a monitoring -g $RG -n $AKS \
  --workspace-resource-id $WS --data-collection-settings dcr-settings.json
```

Add the `Microsoft-Perf` stream (needed for CPU / memory per pod):
```bash
# add "Microsoft-Perf" to the streams list in dcr-settings.json, then:
az aks addon update -a monitoring -g $RG -n $AKS \
  --workspace-resource-id $WS --data-collection-settings dcr-settings.json
az monitor data-collection rule list -g $RG --query "[].{name:name, streams:dataFlows[].streams}" -o json
```

### 3.2 Prometheus scraping (HTTP request count and latency)
```bash
kubectl patch deployment backend-deployment -n focc-ecommerce -p \
 '{"spec":{"template":{"metadata":{"annotations":{"prometheus.io/scrape":"true","prometheus.io/port":"5000","prometheus.io/path":"/metrics"}}}}}'

cat > agentconfig.yaml <<'EOF2'
apiVersion: v1
kind: ConfigMap
metadata:
  name: container-azm-ms-agentconfig
  namespace: kube-system
data:
  schema-version: v1
  config-version: ver1
  prometheus-data-collection-settings: |-
    [prometheus_data_collection_settings.cluster]
        interval = "1m"
        monitor_kubernetes_pods = true
        monitor_kubernetes_pods_namespaces = ["focc-ecommerce"]
EOF2
kubectl apply -f agentconfig.yaml
kubectl get pods -n kube-system | grep -i ama

# generate a little traffic so data appears
for i in 1 2 3 4 5 6 7 8 9 10; do curl -s -o /dev/null http://<FRONTEND-EXTERNAL-IP>/api/products; done
```
Check in **Logs**: `InsightsMetrics | where Origin == "container.azm.ms" | distinct Name, Namespace`

### 3.3 Dashboard tiles (Azure Monitor)
Run each query in **AKS -> Logs**, switch to *Chart*, then **Pin to dashboard** (private dashboard `focc-lab2`).

**Tile 1 - Total HTTP requests**
```kusto
InsightsMetrics
| where Namespace == "prometheus" and Name == "http_requests_total"
| extend Series = tostring(Tags)
| summarize V = max(Val) by Series, bin(TimeGenerated, 1m)
| summarize Total_HTTP_Requests = sum(V) by TimeGenerated
| render timechart
```

**Tile 2 - P95 latency**
```kusto
let b = InsightsMetrics
| where Namespace == "prometheus" and Name == "http_request_duration_seconds_bucket"
| extend T = parse_json(Tags), Series = tostring(Tags)
| extend le = todouble(replace_string(tostring(T.le), "+Inf", "1000"))
| summarize V = max(Val) by Series, le, bin(TimeGenerated, 1m)
| sort by Series asc, TimeGenerated asc
| extend D = iff(Series == prev(Series), V - prev(V), 0.0)
| extend D = iff(D < 0, 0.0, D)
| summarize C = sum(D) by le, TimeGenerated;
// pick the smallest bucket whose cumulative count reaches 95% of the total
let tot = b | where le >= 1000 | project TimeGenerated, Total = C;
b | join kind=inner tot on TimeGenerated
| where Total > 0
| sort by TimeGenerated asc, le asc
| extend Cum = row_cumsum(C, TimeGenerated != prev(TimeGenerated))
| where Cum >= 0.95 * Total
| summarize P95_seconds = min(le) by TimeGenerated
| render timechart
```
> If your own P95 query from the lab differs, keep yours - this one is the same idea (bucket-based percentile).

**Tile 3 - CPU per pod (% of the 100m request)**
```kusto
let pods = KubePodInventory
| where Namespace == "focc-ecommerce" and Name startswith "backend-deployment"
| summarize by PodUid, PodName = Name;
Perf
| where ObjectName == "K8SContainer" and CounterName == "cpuUsageNanoCores"
| extend PodUid = tostring(split(InstanceName, "/")[-2])
| join kind=inner pods on PodUid
| summarize CPU_pct_of_request = avg(CounterValue) / 100000000.0 * 100 by PodName, bin(TimeGenerated, 1m)
| render timechart
```

**Tile 4 - Memory usage (MiB)**
```kusto
let pods = KubePodInventory
| where Namespace == "focc-ecommerce" and Name startswith "backend-deployment"
| summarize by PodUid, PodName = Name;
Perf
| where ObjectName == "K8SContainer" and CounterName == "memoryWorkingSetBytes"
| extend PodUid = tostring(split(InstanceName, "/")[-2])
| join kind=inner pods on PodUid
| summarize Memory_MiB = avg(CounterValue) / 1048576.0 by PodName, bin(TimeGenerated, 1m)
| render timechart
```

**Tile 5 - Active replica count**
```kusto
InsightsMetrics
| where Name == "kube_hpa_status_current_replicas"
| summarize Replicas = max(Val) by bin(TimeGenerated, 1m)
| render timechart
```

### 3.4 Action group and alert rules
```bash
az monitor action-group create -g $RG -n focc-lab2-alerts --short-name focclab2 \
  --action email me <your-email@example.com>
AG=$(az monitor action-group show -g $RG -n focc-lab2-alerts --query id -o tsv)
```
Confirm the e-mail address from the verification mail Azure sends.

**Alert 1 - CPU above 75% (5-minute window)**
```bash
Q1='let pods = KubePodInventory
| where Namespace == "focc-ecommerce" and Name startswith "backend-deployment"
| summarize by PodUid, PodName = Name;
Perf
| where ObjectName == "K8SContainer" and CounterName == "cpuUsageNanoCores"
| extend PodUid = tostring(split(InstanceName, "/")[-2])
| join kind=inner pods on PodUid
| summarize CPU_pct = avg(CounterValue) / 100000000.0 * 100 by PodName, bin(TimeGenerated, 1m)
| where CPU_pct > 75'

az monitor scheduled-query create -g $RG -n "Alert-Backend-HighCPU-75pct" \
  --location $REGION --scopes "$WS" --action-groups "$AG" --severity 2 \
  --window-size 5m --evaluation-frequency 1m \
  --condition "count 'Q1' > 0" --condition-query Q1="$Q1" \
  --description "Backend pod CPU above 75% of its request"
```

**Alert 2 - Pod restarts above 3 in 10 minutes**
```bash
Q2='KubePodInventory
| where Namespace == "focc-ecommerce"
| summarize Restarts = max(PodRestartCount) - min(PodRestartCount) by Name
| where Restarts > 3'

az monitor scheduled-query create -g $RG -n "Alert-Pod-Restarts-Exceeded" \
  --location $REGION --scopes "$WS" --action-groups "$AG" --severity 1 \
  --window-size 10m --evaluation-frequency 5m \
  --condition "count 'Q2' > 0" --condition-query Q2="$Q2" \
  --description "Pod restarts above 3 in 10 minutes"
```

Verify:
```bash
az monitor scheduled-query list -g $RG \
  --query "[].{name:name, enabled:enabled, severity:severity, window:windowSize, every:evaluationFrequency}" -o table
```

---

## Step 4 - Load test and alerting

Keep the test to 3-5 minutes (free Log Analytics ingestion limit: 500 MB/day).

Terminal 1 (Cloud Shell) - watch scaling:
```bash
kubectl get hpa backend-hpa -n focc-ecommerce -w
kubectl get pods -n focc-ecommerce -w
```
Terminal 2 - generate load:
```bash
python load-test/load_test.py --url http://<FRONTEND-EXTERNAL-IP> --concurrency 6 --duration 300
```
Capture: the CPU/replica spike on the dashboard, `kubectl get hpa -w` going 1 -> 3 -> 5 replicas, and the *Alert fired* / *resolved* e-mails.

## Cleanup
```bash
az group delete -n $RG --yes --no-wait
```