"""
SmartOps Monitoring Agent — Production Version

New in this version:
  - Server self-registration on startup (POST /servers/register)
  - Log collection every LOG_COLLECT_INTERVAL seconds
  - Disk-persistent retry buffer (survives restarts)
  - API key authentication (Authorization: Bearer <token>)
"""

import argparse
import os
import platform
import signal
import socket
import sys
import time

import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.config import AgentConfig
from agent.collector import MetricCollector
from agent.log_collector import LogCollector
from agent.sender import MetricSender
from agent.retry import RetryBuffer
from shared.logging_config import setup_logging, get_logger

setup_logging(name="smartops", level=AgentConfig.LOG_LEVEL, log_file=AgentConfig.LOG_FILE)
logger = get_logger("agent.main")

LOG_COLLECT_INTERVAL = int(os.getenv("LOG_COLLECT_INTERVAL", "30"))


class SmartOpsAgent:
    def __init__(self, server_name=AgentConfig.SERVER_NAME, api_url=AgentConfig.API_URL,
                 interval=AgentConfig.INTERVAL, api_key=""):
        self.server_name = server_name
        self.interval = interval
        self.api_key = api_key or os.getenv("SMARTOPS_API_KEY", "")
        self._running = False
        self._server_id = None

        self.collector = MetricCollector(server_name=server_name)
        self.log_collector = LogCollector(server_name=server_name)
        self.sender = MetricSender(
            api_url=api_url, timeout=AgentConfig.TIMEOUT,
            retry_attempts=AgentConfig.RETRY_ATTEMPTS,
            retry_delay=AgentConfig.RETRY_DELAY, api_key=self.api_key,
        )
        self.buffer = RetryBuffer()
        logger.info(f"Agent initialised | server={server_name} | interval={interval}s")

    def start(self):
        self._running = True
        self._register_signals()
        self._register_server()
        logger.info("Agent running. Press Ctrl+C to stop.")

        cycles, errors, last_log_collect = 0, 0, 0.0

        while self._running:
            cycle_start = time.monotonic()

            if not self.buffer.is_empty:
                self._drain_buffer()

            try:
                metrics = self.collector.collect()
                payload = metrics.to_dict()
                sent = self.sender.send_metrics(payload)
                cycles += 1
                if sent:
                    logger.info(
                        f"[cycle={cycles}] Metrics sent | "
                        f"CPU={metrics.cpu_percent:.1f}% MEM={metrics.memory_percent:.1f}%"
                    )
                else:
                    errors += 1
                    self.buffer.push("metrics", payload)
            except Exception as e:
                errors += 1
                logger.error(f"Cycle error: {e}", exc_info=True)

            now = time.monotonic()
            if now - last_log_collect >= LOG_COLLECT_INTERVAL:
                try:
                    self._collect_and_send_logs()
                except Exception as e:
                    logger.debug(f"Log collection error (non-fatal): {e}")
                last_log_collect = now

            elapsed = time.monotonic() - cycle_start
            sleep_for = max(0, self.interval - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)

        logger.info(f"Agent stopped. cycles={cycles} errors={errors}")

    def stop(self):
        logger.info("Stopping agent...")
        self._running = False
        self.sender.close()

    def _register_server(self):
        try:
            mem = psutil.virtual_memory()
            reg = {
                "hostname": self.server_name,
                "ip_address": _get_local_ip(),
                "os_name": platform.system(),
                "os_version": platform.release(),
                "arch": platform.machine(),
                "cpu_cores": psutil.cpu_count(logical=True),
                "cpu_cores_physical": psutil.cpu_count(logical=False) or 1,
                "memory_total_mb": round(mem.total / 1024 / 1024, 0),
                "agent_version": "1.1.0",
            }
            server_id = self.sender.register_server(reg)
            if server_id:
                self._server_id = server_id
                logger.info(f"Server registered | id={server_id}")
            else:
                logger.warning("Registration failed — continuing without server_id")
        except Exception as e:
            logger.warning(f"Registration error (non-fatal): {e}")

    def _collect_and_send_logs(self):
        batch = self.log_collector.collect()
        if batch.total_lines == 0:
            return
        payload = batch.to_dict()
        sent = self.sender.send_logs(payload)
        if sent:
            logger.debug(f"Shipped {batch.total_lines} log lines")
        else:
            self.buffer.push("logs", payload)

    def _drain_buffer(self):
        def _sender(ptype, payload):
            if ptype == "metrics":
                return self.sender.send_metrics(payload)
            elif ptype == "logs":
                return self.sender.send_logs(payload)
            return False
        sent, failed = self.buffer.drain(_sender)
        if sent or failed:
            logger.info(f"Buffer drain: {sent} sent, {failed} failed")

    def _register_signals(self):
        def handler(signum, frame):
            logger.info(f"Signal {signum} — stopping...")
            self.stop()
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)


def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def parse_args():
    parser = argparse.ArgumentParser(description="SmartOps Monitoring Agent")
    parser.add_argument("--server", default=AgentConfig.SERVER_NAME)
    parser.add_argument("--api", default=AgentConfig.API_URL)
    parser.add_argument("--interval", type=int, default=AgentConfig.INTERVAL)
    parser.add_argument("--api-key", default=os.getenv("SMARTOPS_API_KEY", ""))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    agent = SmartOpsAgent(
        server_name=args.server, api_url=args.api,
        interval=args.interval, api_key=args.api_key,
    )
    agent.start()
