#!/usr/bin/env python3
"""
Mini E-commerce Store — Load Testing Tool
Fundamentals of Cloud Computing (FoCC) Lab 2

A beginner-friendly concurrent load generator using only the Python standard library.
Simulates realistic shopping traffic combined with controlled CPU load to trigger
Kubernetes Horizontal Pod Autoscaler (HPA) and Azure Monitor alerts.

Usage:
  python load_test.py --url http://localhost:8080 --concurrency 6 --duration 180
"""

import sys
import time
import urllib.request
import urllib.error
import json
import argparse
import random
import threading
from datetime import datetime

# Thread-safe metrics collector
class MetricsCollector:
    def __init__(self):
        self.lock = threading.Lock()
        self.total_requests = 0
        self.successful_requests = 0
        self.client_errors = 0      # 4xx
        self.server_errors = 0      # 5xx
        self.network_errors = 0     # Timeouts / connection refused
        self.latencies = []         # In milliseconds

    def record(self, status_code, latency_ms, error=None):
        with self.lock:
            self.total_requests += 1
            if latency_ms is not None:
                self.latencies.append(latency_ms)

            if error:
                self.network_errors += 1
            elif status_code and 200 <= status_code < 300:
                self.successful_requests += 1
            elif status_code and 400 <= status_code < 500:
                self.client_errors += 1
            elif status_code and 500 <= status_code < 600:
                self.server_errors += 1
            else:
                self.network_errors += 1

    def snapshot(self):
        with self.lock:
            total = self.total_requests
            success = self.successful_requests
            errors = self.client_errors + self.server_errors + self.network_errors
            err_rate = (errors / total * 100.0) if total > 0 else 0.0
            
            if self.latencies:
                sorted_lats = sorted(self.latencies)
                avg_lat = sum(sorted_lats) / len(sorted_lats)
                p95_idx = int(0.95 * len(sorted_lats))
                p95_lat = sorted_lats[min(p95_idx, len(sorted_lats) - 1)]
            else:
                avg_lat = 0.0
                p95_lat = 0.0

            return {
                "total": total,
                "success": success,
                "errors": errors,
                "error_rate": err_rate,
                "avg_lat": avg_lat,
                "p95_lat": p95_lat,
            }

    def print_final_summary(self, target_url, elapsed_time):
        with self.lock:
            total = self.total_requests
            success = self.successful_requests
            client_err = self.client_errors
            server_err = self.server_errors
            net_err = self.network_errors
            total_err = client_err + server_err + net_err
            err_rate = (total_err / total * 100.0) if total > 0 else 0.0
            rps = (total / elapsed_time) if elapsed_time > 0 else 0.0

            lats = sorted(self.latencies) if self.latencies else [0]
            avg_lat = sum(lats) / len(lats)
            min_lat = lats[0]
            max_lat = lats[-1]
            p50 = lats[int(0.50 * len(lats))]
            p90 = lats[min(int(0.90 * len(lats)), len(lats) - 1)]
            p95 = lats[min(int(0.95 * len(lats)), len(lats) - 1)]
            p99 = lats[min(int(0.99 * len(lats)), len(lats) - 1)]

        print("\n" + "=" * 70)
        print("          LOAD TEST RESULTS — FINAL LAB SUMMARY")
        print("=" * 70)
        print(f" Timestamp:              {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f" Target Endpoint:        {target_url}")
        print(f" Total Duration:         {elapsed_time:.1f} seconds")
        print(f" Total Requests:         {total}")
        print(f" Successful (2xx):       {success}")
        print(f" Client Errors (4xx):    {client_err}")
        print(f" Server Errors (5xx):    {server_err}")
        print(f" Network / Conn Errors:  {net_err}")
        print(f" Overall Error Rate:     {err_rate:.2f} %")
        print(f" Average Throughput:     {rps:.2f} requests/sec")
        print("-" * 70)
        print(" LATENCY DISTRIBUTION (Milliseconds):")
        print(f"   Min:   {min_lat:8.1f} ms")
        print(f"   Avg:   {avg_lat:8.1f} ms")
        print(f"   P50:   {p50:8.1f} ms  (Median)")
        print(f"   P90:   {p90:8.1f} ms")
        print(f"   P95:   {p95:8.1f} ms  [Key metric for Azure alert/SLA]")
        print(f"   P99:   {p99:8.1f} ms")
        print(f"   Max:   {max_lat:8.1f} ms")
        print("=" * 70)
        print(" Lab Report Checklist:")
        print(" [x] Capture this terminal output as evidence of test execution.")
        print(" [x] Compare P95 latency against Azure Monitor / Container Insights.")
        print(" [x] Record replica scale changes observed via: kubectl get hpa -w")
        print("=" * 70 + "\n")


def send_request(url, timeout=10.0):
    """Send a single HTTP GET request and measure response time."""
    start = time.perf_counter()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "FoCC-Lab2-LoadTester/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            _ = response.read()
            latency = (time.perf_counter() - start) * 1000.0
            return response.getcode(), latency, None
    except urllib.error.HTTPError as e:
        latency = (time.perf_counter() - start) * 1000.0
        return e.code, latency, None
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000.0
        return None, latency, str(e)


def worker_loop(worker_id, base_url, cpu_ratio, load_duration, stop_event, collector):
    """Worker thread generating continuous traffic."""
    # Build endpoint URLs
    catalog_url = f"{base_url}/api/products"
    cpu_load_url = f"{base_url}/api/test-load?duration={load_duration}"

    while not stop_event.is_set():
        # Decide between catalog browsing and CPU load test based on cpu_ratio
        if random.random() < cpu_ratio:
            target = cpu_load_url
        else:
            target = catalog_url

        status, latency, err = send_request(target)
        collector.record(status, latency, err)

        # Micro sleep to prevent local socket exhaustion
        time.sleep(0.05)


def progress_reporter(collector, duration, stop_event):
    """Print timestamped progress logs suitable for lab screenshots."""
    start_time = time.time()
    while not stop_event.is_set():
        time.sleep(10)
        elapsed = time.time() - start_time
        if elapsed > duration:
            break
        snap = collector.snapshot()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[{timestamp}] Elapsed: {int(elapsed):3d}s/{duration}s | "
            f"Reqs: {snap['total']:4d} | Success: {snap['success']:4d} | "
            f"Errors: {snap['errors']:2d} ({snap['error_rate']:.1f}%) | "
            f"Avg Lat: {snap['avg_lat']:6.1f}ms | P95: {snap['p95_lat']:6.1f}ms"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Mini E-commerce Load Test Script — FoCC Lab 2"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8080",
        help="Target application URL (e.g. http://localhost:8080 or http://<EXTERNAL_IP>)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=6,
        help="Number of concurrent worker threads (default: 6)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=180,
        help="Total test duration in seconds (default: 180s = 3 minutes)"
    )
    parser.add_argument(
        "--cpu-ratio",
        type=float,
        default=0.6,
        help="Fraction of requests sent to /api/test-load (0.0 to 1.0, default: 0.6)"
    )
    parser.add_argument(
        "--load-duration",
        type=float,
        default=1.5,
        help="Duration param for /api/test-load?duration=X in seconds (max 5.0, default: 1.5)"
    )

    args = parser.parse_args()

    # Normalize target URL
    base_url = args.url.rstrip("/")

    print("=" * 70)
    print("      FoCC Lab 2: Mini E-Commerce Controlled Load Generator")
    print("=" * 70)
    print(f" Target Base URL:       {base_url}")
    print(f" Concurrency (Threads): {args.concurrency}")
    print(f" Test Duration:         {args.duration} seconds ({args.duration / 60:.1f} minutes)")
    print(f" CPU Load Ratio:        {int(args.cpu_ratio * 100)}% CPU / {int((1 - args.cpu_ratio) * 100)}% Catalog")
    print(f" CPU Burn per Request:  {args.load_duration} seconds")
    print("=" * 70)
    print(" Pre-flight check: Verifying target application health...")

    # Quick pre-flight check
    status, lat, err = send_request(f"{base_url}/health/live", timeout=5.0)
    if err or status != 200:
        print(f"[ERROR] Pre-flight health check failed on {base_url}/health/live!")
        print(f"        Status: {status}, Error: {err}")
        print("Please ensure your Docker Compose or AKS application is running before testing.")
        sys.exit(1)
    print(f"[OK] Pre-flight check passed! Backend live. (Response time: {lat:.1f}ms)\n")

    print(f"Starting test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    print("Press Ctrl+C at any time to gracefully halt the test and view partial results.\n")
    print("--- LIVE TEST LOGS (Take screenshots here) ---")

    collector = MetricsCollector()
    stop_event = threading.Event()

    # Start progress reporter thread
    reporter_thread = threading.Thread(
        target=progress_reporter,
        args=(collector, args.duration, stop_event),
        daemon=True
    )
    reporter_thread.start()

    # Start worker threads
    workers = []
    start_time = time.time()
    for i in range(args.concurrency):
        t = threading.Thread(
            target=worker_loop,
            args=(i, base_url, args.cpu_ratio, args.load_duration, stop_event, collector),
            daemon=True
        )
        t.start()
        workers.append(t)

    # Main thread sleeps for duration or waits for Ctrl+C
    try:
        while (time.time() - start_time) < args.duration:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\n[INFO] Interrupt signal received! Stopping worker threads safely...")
    finally:
        stop_event.set()
        for t in workers:
            t.join(timeout=2.0)

    elapsed_time = time.time() - start_time
    collector.print_final_summary(base_url, elapsed_time)


if __name__ == "__main__":
    main()
