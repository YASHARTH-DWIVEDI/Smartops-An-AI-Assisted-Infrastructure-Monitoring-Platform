"""
Seed Data Generator — populates the SmartOps database with realistic
historical metrics for testing the dashboard.

Usage:
    python scripts/seed_data.py
    python scripts/seed_data.py --servers 3 --hours 6 --interval 10
"""

import argparse
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests

API_URL = os.getenv("AGENT_API_URL", "http://localhost:8000")
ENDPOINT = f"{API_URL}/api/metrics"


def generate_metrics(
    server_name: str,
    timestamp_offset_s: float = 0,
    spike: bool = False,
) -> dict:
    """Generate a single realistic metric snapshot."""
    # Base values with some noise
    base_cpu = random.gauss(35, 12)
    base_mem = random.gauss(58, 8)
    base_disk = random.gauss(47, 5)

    # Add time-based oscillation (simulates daily load pattern)
    hour_factor = math.sin(timestamp_offset_s / 3600 * math.pi / 12)
    base_cpu += hour_factor * 15

    if spike:
        # Random resource spike
        spike_type = random.choice(["cpu", "memory", "disk", "all"])
        if spike_type in ("cpu", "all"):
            base_cpu = random.uniform(88, 99)
        if spike_type in ("memory", "all"):
            base_mem = random.uniform(88, 97)
        if spike_type in ("disk", "all"):
            base_disk = random.uniform(83, 92)

    cpu = max(0.5, min(99.9, base_cpu))
    mem = max(20.0, min(98.0, base_mem))
    disk = max(30.0, min(95.0, base_disk))

    total_mem_mb = random.choice([4096, 8192, 16384])
    total_disk_gb = random.choice([100, 200, 500, 1000])

    return {
        "server_name": server_name,
        "cpu_percent": round(cpu, 2),
        "memory_percent": round(mem, 2),
        "memory_used_mb": round(mem / 100 * total_mem_mb, 1),
        "memory_total_mb": float(total_mem_mb),
        "disk_percent": round(disk, 2),
        "disk_used_gb": round(disk / 100 * total_disk_gb, 2),
        "disk_total_gb": float(total_disk_gb),
        "net_bytes_sent": random.randint(1024, 1024 * 1024 * 5),
        "net_bytes_recv": random.randint(1024, 1024 * 1024 * 10),
        "uptime_seconds": random.uniform(3600, 86400 * 30),
        "load_avg_1m": round(random.uniform(0.1, cpu / 25), 2),
        "load_avg_5m": round(random.uniform(0.1, cpu / 30), 2),
        "load_avg_15m": round(random.uniform(0.1, cpu / 35), 2),
        "process_count": random.randint(80, 350),
        "top_processes": [
            {
                "pid": random.randint(1000, 60000),
                "name": random.choice(["nginx", "python3", "node", "postgres", "redis-server", "java"]),
                "cpu_percent": round(random.uniform(0.1, min(cpu * 0.4, 40)), 2),
                "memory_percent": round(random.uniform(0.1, 8.0), 2),
                "status": "running",
            }
            for _ in range(random.randint(2, 5))
        ],
    }


def seed(
    server_names: list,
    hours_back: int = 6,
    interval_seconds: int = 10,
    spike_probability: float = 0.05,
):
    total_points = int(hours_back * 3600 / interval_seconds) * len(server_names)
    print(f"\n🌱 SmartOps Seed Data Generator")
    print(f"   Servers:    {', '.join(server_names)}")
    print(f"   Hours back: {hours_back}")
    print(f"   Interval:   {interval_seconds}s")
    print(f"   Total:      ~{total_points} data points\n")

    # Check API reachable
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        if not r.ok:
            print(f"❌ API health check failed: {r.status_code}")
            sys.exit(1)
        print(f"✅ API reachable at {API_URL}\n")
    except Exception as e:
        print(f"❌ Cannot reach API at {API_URL}: {e}")
        print("   Start the API first: cd api && uvicorn main:app --port 8000")
        sys.exit(1)

    sent = 0
    errors = 0
    start_ts = datetime.utcnow() - timedelta(hours=hours_back)

    steps = int(hours_back * 3600 / interval_seconds)

    for step in range(steps):
        offset_s = step * interval_seconds
        current_ts = start_ts + timedelta(seconds=offset_s)
        spike = random.random() < spike_probability

        for server in server_names:
            payload = generate_metrics(server, offset_s, spike=spike)

            try:
                r = requests.post(ENDPOINT, json=payload, timeout=10)
                if r.ok:
                    sent += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"   ⚠️  Send error: {e}")

        # Progress indicator
        if (step + 1) % 50 == 0 or step == steps - 1:
            pct = (step + 1) / steps * 100
            print(f"   [{pct:5.1f}%] {sent} sent, {errors} errors", end="\r")
        elif (step + 1) % 10 == 0:
            time.sleep(0.01)  # Small delay to avoid overwhelming local API

    print(f"\n\n✅ Seeding complete: {sent} records sent, {errors} errors.")
    print(f"\nOpen your dashboard: http://localhost:8501\n")


def main():
    parser = argparse.ArgumentParser(description="Seed SmartOps with test data")
    parser.add_argument("--servers", type=int, default=2, help="Number of mock servers")
    parser.add_argument("--hours", type=int, default=6, help="Hours of history to generate")
    parser.add_argument("--interval", type=int, default=10, help="Interval between readings (s)")
    parser.add_argument("--api", default=API_URL, help="API URL")
    args = parser.parse_args()

    global API_URL, ENDPOINT
    API_URL = args.api
    ENDPOINT = f"{API_URL}/api/metrics"

    server_names = [f"server-{chr(65 + i):02s}" for i in range(args.servers)]
    # Fix naming
    server_names = [f"prod-web-0{i+1}" for i in range(args.servers)]

    seed(
        server_names=server_names,
        hours_back=args.hours,
        interval_seconds=args.interval,
    )


if __name__ == "__main__":
    main()
