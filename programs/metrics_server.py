#!/usr/bin/env python3
"""
Lightweight Prometheus metrics exporter for the timelapse system.

Zero external dependencies - uses only Python stdlib.
Designed for Raspberry Pi Zero (single-core ARM, 512MB RAM).

Serves a /metrics endpoint in Prometheus text exposition format.
Collects metrics by reading:
  - /tmp/timelapse_status.json (written by the C++ timelapse binary)
  - Filesystem state (pics/, videos/, backup markers)
  - System stats (disk usage, CPU temperature)
"""

import json
import os
import shutil
import configparser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# --- Project Path Setup ---
SCRIPT_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_PATH.parent
CONF_DIR = PROJECT_ROOT / "conf"
PICS_DIR = PROJECT_ROOT / "pics"
VIDEOS_DIR = PROJECT_ROOT / "videos"
LOGS_DIR = PROJECT_ROOT / "logs"

STATUS_FILE = Path("/tmp/timelapse_status.json")
CPU_TEMP_FILE = Path("/sys/class/thermal/thermal_zone0/temp")

# Defaults
DEFAULT_PORT = 8080
DEFAULT_BIND = "0.0.0.0"


def load_config():
    """Load metrics config from timelapse.conf."""
    config = configparser.ConfigParser()
    config_path = CONF_DIR / "timelapse.conf"
    config.read(config_path)

    device_id = config.get("DEVICE", "id", fallback="unknown")
    port = config.getint("METRICS", "port", fallback=DEFAULT_PORT)
    bind = config.get("METRICS", "bind", fallback=DEFAULT_BIND)

    return device_id, port, bind


def read_status_file():
    """Read the JSON status file written by the C++ binary."""
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return None


def get_cpu_temperature():
    """Read CPU temperature from sysfs (millidegrees -> celsius)."""
    try:
        if CPU_TEMP_FILE.exists():
            temp_str = CPU_TEMP_FILE.read_text().strip()
            return int(temp_str) / 1000.0
    except (ValueError, IOError):
        pass
    return None


def get_disk_usage():
    """Get disk usage for the project root's filesystem."""
    try:
        usage = shutil.disk_usage(PROJECT_ROOT)
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": (usage.used / usage.total) * 100,
        }
    except OSError:
        return None


def count_todays_photos():
    """Count photos captured today by checking the pics directory."""
    today = datetime.now().strftime("%Y%m%d")
    for item in PICS_DIR.iterdir() if PICS_DIR.exists() else []:
        if item.is_dir() and item.name.startswith(today) and item.name.endswith("_pics"):
            return len([f for f in item.iterdir() if f.suffix == ".jpg"])
    return 0


def get_latest_video_info():
    """Get info about the most recent video file."""
    if not VIDEOS_DIR.exists():
        return None

    videos = sorted(
        [f for f in VIDEOS_DIR.iterdir() if f.name.endswith("_timelapse.mp4")],
        key=lambda f: f.name,
        reverse=True,
    )
    if not videos:
        return None

    latest = videos[0]
    backed_up = (VIDEOS_DIR / f"{latest.name}.backed_up").exists()
    try:
        size = latest.stat().st_size
    except OSError:
        size = 0

    return {"name": latest.name, "size_bytes": size, "backed_up": backed_up}


def check_process_running():
    """Check if the timelapse C++ binary is currently running."""
    try:
        # Look for the process by name in /proc (Linux-specific)
        for pid_dir in Path("/proc").iterdir():
            if not pid_dir.name.isdigit():
                continue
            try:
                cmdline = (pid_dir / "cmdline").read_text()
                if "programs/timelapse" in cmdline:
                    return True
            except (IOError, PermissionError):
                continue
    except (IOError, PermissionError):
        pass
    return False


def collect_metrics(device_id):
    """Collect all metrics and return as Prometheus text exposition format."""
    lines = []

    def gauge(name, value, help_text, labels=None):
        """Append a gauge metric in Prometheus format."""
        label_str = f'{{device="{device_id}"'
        if labels:
            for k, v in labels.items():
                label_str += f',{k}="{v}"'
        label_str += "}"
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name}{label_str} {value}")

    # --- Status from C++ binary ---
    status = read_status_file()
    if status:
        # Map status string to numeric for alerting
        status_map = {
            "waiting": 0, "capturing": 1, "creating_video": 2, "finished": 3
        }
        status_val = status_map.get(status.get("status", ""), -1)
        gauge("timelapse_status", status_val,
              "Current status (0=waiting, 1=capturing, 2=creating_video, 3=finished, -1=unknown)")

        gauge("timelapse_photos_captured_today", status.get("photos_captured", 0),
              "Number of photos captured today")
        gauge("timelapse_photos_expected_today", status.get("expected_photos", 0),
              "Number of photos expected today")
        gauge("timelapse_capture_errors_total", status.get("capture_errors", 0),
              "Total capture errors today")
        gauge("timelapse_last_capture_success", 1 if status.get("last_capture_success") else 0,
              "Whether the last capture succeeded (1) or failed (0)")
        gauge("timelapse_last_capture_timestamp", status.get("last_capture_timestamp", 0),
              "Unix timestamp of the last capture")
        gauge("timelapse_last_capture_duration_ms", status.get("last_capture_duration_ms", 0),
              "Duration of the last capture in milliseconds")
        gauge("timelapse_status_file_updated_at", status.get("updated_at", 0),
              "Unix timestamp when the status file was last updated")

        if status.get("expected_photos", 0) > 0:
            progress = (status.get("photos_captured", 0) / status["expected_photos"]) * 100
            gauge("timelapse_capture_progress_percent", f"{progress:.1f}",
                  "Capture progress as percentage")
    else:
        gauge("timelapse_status", -1,
              "Current status (0=waiting, 1=capturing, 2=creating_video, 3=finished, -1=unknown)")

    # --- Process running ---
    gauge("timelapse_process_running", 1 if check_process_running() else 0,
          "Whether the timelapse binary is currently running")

    # --- Disk usage ---
    disk = get_disk_usage()
    if disk:
        gauge("timelapse_disk_usage_percent", f"{disk['percent']:.1f}",
              "Disk usage percentage for the timelapse filesystem")
        gauge("timelapse_disk_used_bytes", disk["used"],
              "Disk space used in bytes")
        gauge("timelapse_disk_free_bytes", disk["free"],
              "Disk space free in bytes")
        gauge("timelapse_disk_total_bytes", disk["total"],
              "Total disk space in bytes")

    # --- CPU temperature ---
    cpu_temp = get_cpu_temperature()
    if cpu_temp is not None:
        gauge("timelapse_cpu_temperature_celsius", f"{cpu_temp:.1f}",
              "CPU temperature in degrees Celsius")

    # --- Latest video info ---
    video = get_latest_video_info()
    if video:
        gauge("timelapse_last_video_size_bytes", video["size_bytes"],
              "Size of the most recent video in bytes")
        gauge("timelapse_last_video_backed_up", 1 if video["backed_up"] else 0,
              "Whether the most recent video has been backed up")

    # --- Photo directory count (number of days with photos on disk) ---
    if PICS_DIR.exists():
        photo_dirs = [d for d in PICS_DIR.iterdir() if d.is_dir() and d.name.endswith("_pics")]
        backed_up_dirs = [d for d in photo_dirs if (d / ".backed_up").exists()]
        gauge("timelapse_photo_dirs_total", len(photo_dirs),
              "Total photo directories on disk")
        gauge("timelapse_photo_dirs_backed_up", len(backed_up_dirs),
              "Photo directories that have been backed up")

    lines.append("")  # trailing newline
    return "\n".join(lines)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves Prometheus metrics."""

    device_id = "unknown"

    def do_GET(self):
        if self.path == "/metrics":
            body = collect_metrics(self.device_id)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default request logging to reduce noise."""
        pass


def main():
    device_id, port, bind = load_config()
    MetricsHandler.device_id = device_id

    server = HTTPServer((bind, port), MetricsHandler)
    print(f"Timelapse metrics server starting on {bind}:{port}")
    print(f"Device: {device_id}")
    print(f"Metrics: http://{bind}:{port}/metrics")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down metrics server")
        server.shutdown()


if __name__ == "__main__":
    os.chdir(PROJECT_ROOT)
    main()
