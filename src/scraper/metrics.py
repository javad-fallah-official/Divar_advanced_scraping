import json
import logging
import os
import time
from datetime import datetime

try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # type: ignore


_LOG_DIR = os.path.join("logs")
_LOG_PATH = os.path.join(_LOG_DIR, "scrape.jsonl")


def _ensure_paths():
    os.makedirs(_LOG_DIR, exist_ok=True)
    if not os.path.exists(_LOG_PATH):
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            pass


def now_iso():
    return datetime.utcnow().isoformat()


def log_event(event: str, **fields):
    _ensure_paths()
    payload = {"ts": now_iso(), "event": event}
    payload.update(fields)
    line = json.dumps(payload, ensure_ascii=False)
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def sample_system():
    pid = os.getpid()
    info = {"pid": pid}
    if psutil is not None:
        p = psutil.Process(pid)
        cpu = psutil.cpu_percent(interval=None)
        mem = p.memory_info()
        io = psutil.net_io_counters()
        info.update({
            "cpu_percent": cpu,
            "rss_bytes": int(mem.rss),
            "vms_bytes": int(mem.vms),
            "net_bytes_sent": int(io.bytes_sent),
            "net_bytes_recv": int(io.bytes_recv),
        })
    return info


class Timer:
    def __init__(self):
        self.t0 = time.perf_counter()

    def ms(self):
        return (time.perf_counter() - self.t0) * 1000.0


def time_call(name: str):
    def deco(fn):
        def wrapper(*args, **kwargs):
            t = Timer()
            try:
                return fn(*args, **kwargs)
            finally:
                log_event("timer", name=name, ms=t.ms())
        return wrapper
    return deco

