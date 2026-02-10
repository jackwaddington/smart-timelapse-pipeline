# Observability Specification (Lightweight)

## Design Constraints

This runs on a Raspberry Pi Zero (1GHz, 512MB RAM) that is already:
- Capturing a photo every ~30 seconds all day
- Spending ~15 minutes encoding video at end of day
- Running rsync backups and YouTube uploads

Observability must add **near-zero overhead** during capture and **zero overhead** during video encoding. No frameworks. No background scraping. Minimal dependencies.

## Architecture

Three layers, in priority order:

| Layer | Overhead | Dependencies | Purpose |
|-------|----------|--------------|---------|
| 1. Status file | ~0 (one file write) | None | Machine-readable state |
| 2. Status server | ~5MB idle | None (stdlib) | Remote access without SSH |
| 3. Error notifications | ~0 (on error only) | `requests` | Know when something breaks |

Prometheus/Grafana integration is a **nice-to-have** add-on, served from the same status server with no extra processes.

---

## Layer 1: Status File (Core)

### Purpose
Existing programs (C++ timelapse, Python scripts) write their state to a shared JSON file. This is the single source of truth. Costs one file write — something the system already does hundreds of times a day for photos.

### File Location
```
/tmp/timelapse_status.json
```

Using `/tmp` so it's on tmpfs (RAM-backed) — no SD card wear, instant reads/writes.

### Written By

| Program | When | Fields Updated |
|---------|------|----------------|
| `timelapse` (C++) | After each capture | `status`, `photos_captured`, `last_capture_*` |
| `timelapse` (C++) | During video creation | `status` → `"creating_video"` |
| `scheduler.py` | After generating schedule | `today.date`, `today.start_time`, `today.end_time`, `today.interval`, `today.expected_photos` |
| `manager.py` | After backup/upload | `last_video.*`, `last_backup_time` |
| `disk_cleanup.py` | After cleanup runs | `disk_percent`, `disk_free_bytes` |

### File Format

```json
{
  "device_id": "Pi0Cam",
  "status": "capturing",
  "updated_at": "2026-02-08T14:23:45",
  "uptime_seconds": 86400,
  "disk_percent": 68.5,
  "disk_free_bytes": 5100000000,
  "cpu_temperature_celsius": 45.2,
  "today": {
    "date": "2026-02-08",
    "photos_captured": 342,
    "expected_photos": 750,
    "start_time": "07:15:00",
    "end_time": "17:30:00",
    "interval_seconds": 45
  },
  "last_capture": {
    "time": "2026-02-08T14:23:45",
    "filename": "20260208_Pi0Cam_0342.jpg",
    "success": true,
    "duration_ms": 1234
  },
  "last_video": {
    "date": "2026-02-07",
    "filename": "20260207_Pi0Cam_timelapse.mp4",
    "duration_seconds": 32,
    "photos_used": 750,
    "backed_up": true,
    "youtube_url": "https://youtu.be/abc123"
  },
  "errors": []
}
```

### Status Values

| Status | Meaning |
|--------|---------|
| `idle` | Outside capture hours, nothing running |
| `waiting` | Timelapse started, waiting for sunrise |
| `capturing` | Actively taking photos |
| `creating_video` | Encoding video from today's photos |
| `backing_up` | Running rsync to NAS |
| `uploading` | Uploading to YouTube |
| `error` | Something is wrong (see `errors` array) |

### Implementation: Status Writer Module

A small shared module used by all programs to safely update the status file.

```python
# programs/status_writer.py

import json
import os
import time
import shutil

STATUS_FILE = "/tmp/timelapse_status.json"

def read_status():
    """Read current status, return empty dict if missing."""
    try:
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def update_status(**fields):
    """Merge fields into status file. Atomic write via rename."""
    status = read_status()
    for key, value in fields.items():
        if isinstance(value, dict) and isinstance(status.get(key), dict):
            status[key].update(value)
        else:
            status[key] = value
    status["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(status, f, indent=2)
    os.rename(tmp, STATUS_FILE)
```

For the C++ timelapse program, equivalent logic: read JSON, update fields, write to tmp, rename. Use a lightweight JSON library already in use or `nlohmann/json` (header-only).

### Checking Status Manually

Without any server running, you can always check status via SSH:
```bash
ssh pi cat /tmp/timelapse_status.json | python3 -m json.tool
```

---

## Layer 2: Status Server (Optional Service)

### Purpose
Serve the status file over HTTP so you can check on the Pi from a browser or `curl` without SSH. Also serves latest photo/video and optionally exposes a `/metrics` endpoint for Prometheus.

### Design
- Python stdlib `http.server` — **zero pip dependencies**
- Runs as a systemd service, idle 99.9% of the time
- ~5MB RAM when idle, wakes only on incoming requests
- **Does not run during video encoding** (systemd can be configured to lower priority, but it's so lightweight it doesn't matter)

### Endpoints

```
GET /health
    → {"status": "ok", "uptime_seconds": 86400}

GET /status
    → Contents of /tmp/timelapse_status.json

GET /latest/photo
    → Serves most recent .jpg (image/jpeg)

GET /latest/video
    → Serves most recent .mp4 (video/mp4)

GET /logs?lines=50&level=error
    → Returns recent log lines (default 50, filterable)

GET /config
    → Returns timelapse.conf (sanitized, no secrets)
```

### Implementation

```python
# programs/status_server.py

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import glob

STATUS_FILE = "/tmp/timelapse_status.json"

class StatusHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/health":
            self._json_response({"status": "ok"})

        elif self.path == "/status":
            self._serve_file(STATUS_FILE, "application/json")

        elif self.path == "/latest/photo":
            self._serve_latest("pics", "*.jpg", "image/jpeg")

        elif self.path == "/latest/video":
            self._serve_latest("videos", "*.mp4", "video/mp4")

        else:
            self.send_error(404)

    def _json_response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(data))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404)

    def _serve_latest(self, directory, pattern, content_type):
        files = sorted(glob.glob(f"{directory}/{pattern}"))
        if files:
            self._serve_file(files[-1], content_type)
        else:
            self.send_error(404, "No files found")

    def log_message(self, format, *args):
        pass  # Suppress default stderr logging

if __name__ == "__main__":
    port = 8080
    server = HTTPServer(("0.0.0.0", port), StatusHandler)
    server.serve_forever()
```

### Systemd Service

```ini
# /etc/systemd/system/timelapse-status.service
[Unit]
Description=Timelapse Status Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/auto-timelapse
ExecStart=/usr/bin/python3 programs/status_server.py
Restart=always
RestartSec=30
Nice=19
CPUQuota=5%
MemoryMax=32M

[Install]
WantedBy=multi-user.target
```

Key settings for Pi Zero:
- `Nice=19` — lowest scheduling priority, never competes with capture/video
- `CPUQuota=5%` — hard limit, can never steal CPU from ffmpeg/opencv
- `MemoryMax=32M` — killed if it ever leaks beyond this

### Port Configuration

```ini
# conf/timelapse.conf
[OBSERVABILITY]
status_server_enabled = true
status_server_port = 8080
status_server_bind = 0.0.0.0
```

---

## Layer 3: Error Notifications

### Purpose
Get a message on your phone when something goes wrong. Only fires on errors — no polling, no background process, no ongoing resource use.

### Design
- Called directly from existing programs when errors occur
- Single HTTP POST to a webhook — takes milliseconds
- No daemon, no queue, no retry logic (if the notification fails, it's logged)
- Uses `requests` library (already a dependency for YouTube upload)

### Notification Events

Only notify on things that need attention:

| Event | Severity | When |
|-------|----------|------|
| Camera error (3+ consecutive) | ERROR | Capture loop in timelapse |
| Video creation failed | ERROR | End of timelapse |
| Disk warning (>80%) | WARNING | disk_cleanup.py |
| Disk critical (>90%) | ERROR | disk_cleanup.py |
| Backup failed | ERROR | manager.py |
| YouTube upload failed | WARNING | manager.py |
| Schedule generation failed | WARNING | scheduler.py |

Note: We do **not** notify on every capture, every video, or every successful backup. Only problems.

### Optional Info Notifications

Can be enabled for people who want a daily summary:

| Event | Severity | When |
|-------|----------|------|
| Daily summary | INFO | End of manager.py run (23:00) |
| Video created | INFO | End of timelapse |

### Supported Channels

| Channel | Config Key | Why |
|---------|------------|-----|
| Telegram | `telegram_bot_token`, `telegram_chat_id` | Free, easy setup, works on phone |
| Discord | `discord_webhook_url` | Single URL, no auth needed |
| Generic webhook | `webhook_url` | Home Assistant, Slack, anything |

Email intentionally excluded — requires SMTP setup, dependencies, and is slower to check than a phone notification.

### Implementation

```python
# programs/notifier.py

import requests
import logging

logger = logging.getLogger(__name__)

def notify(message, level="ERROR", config=None):
    """Send notification to all enabled channels. Fire-and-forget."""
    if config is None:
        config = load_notification_config()

    min_level = config.get("min_level", "WARNING")
    if _level_value(level) < _level_value(min_level):
        return

    if config.get("telegram_enabled"):
        _send_telegram(config, message)

    if config.get("discord_enabled"):
        _send_discord(config, message)

    if config.get("webhook_enabled"):
        _send_webhook(config, message, level)


def _send_telegram(config, message):
    try:
        url = f"https://api.telegram.org/bot{config['telegram_bot_token']}/sendMessage"
        requests.post(url, json={
            "chat_id": config["telegram_chat_id"],
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


def _send_discord(config, message):
    try:
        requests.post(config["discord_webhook_url"], json={
            "content": message
        }, timeout=10)
    except Exception as e:
        logger.warning(f"Discord notification failed: {e}")


def _send_webhook(config, message, level):
    try:
        requests.post(config["webhook_url"], json={
            "message": message,
            "level": level,
            "device_id": config.get("device_id", "unknown")
        }, timeout=10)
    except Exception as e:
        logger.warning(f"Webhook notification failed: {e}")


def _level_value(level):
    return {"INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}.get(level, 0)
```

### Usage in Existing Programs

```python
# In manager.py, after backup fails:
from notifier import notify
notify(f"Backup failed for {date}: {error}", level="ERROR")

# In disk_cleanup.py, when disk is critical:
notify(f"Disk at {percent}% - emergency cleanup running", level="ERROR")
```

For C++, the timelapse program can write errors to the status file's `errors` array. A small cron job or the status server can check for new errors and fire notifications. This avoids adding HTTP dependencies to the C++ code.

### Daily Summary (Optional)

If `daily_summary_enabled = true`, `manager.py` sends a summary at the end of its nightly run:

```
Pi0Cam Daily Summary - 2026-02-08

Photos: 750 captured
Video: 32 seconds
Disk: 68% used (5.1GB free)
Backup: Complete
YouTube: Uploaded

No errors today.
```

### Configuration

```ini
# conf/timelapse.conf
[NOTIFICATIONS]
enabled = true
min_level = WARNING

# Telegram (recommended - free, easy)
telegram_enabled = false
telegram_bot_token =
telegram_chat_id =

# Discord
discord_enabled = false
discord_webhook_url =

# Generic webhook (Home Assistant, Slack, etc.)
webhook_enabled = false
webhook_url =

# Daily summary
daily_summary_enabled = false
```

---

## Nice-to-Have: Prometheus Metrics Endpoint

### Purpose
If you're already running Prometheus/Grafana elsewhere on your network, the status server can expose a `/metrics` endpoint. This adds **zero extra processes** — it's just another route on the existing status server.

### Design
- No `prometheus-client` pip package needed
- The `/metrics` endpoint reads `/tmp/timelapse_status.json` and formats it as Prometheus text
- Prometheus scrapes it every 30-60s — one tiny HTTP request
- All the work happens on the Prometheus server, not the Pi

### Metrics Endpoint

```
GET /metrics
    → Prometheus text exposition format
```

### Implementation

Added to `status_server.py`:

```python
def _prometheus_metrics(self):
    """Generate Prometheus text format from status file."""
    status = read_status_file()
    device = status.get("device_id", "unknown")
    lines = []

    def gauge(name, value, help_text=""):
        if value is not None:
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f'{name}{{device="{device}"}} {value}')

    def counter(name, value, help_text=""):
        if value is not None:
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} counter")
            lines.append(f'{name}{{device="{device}"}} {value}')

    # System
    gauge("timelapse_disk_usage_percent", status.get("disk_percent"),
          "Disk usage percentage")
    gauge("timelapse_disk_free_bytes", status.get("disk_free_bytes"),
          "Free disk space in bytes")
    gauge("timelapse_cpu_temperature_celsius", status.get("cpu_temperature_celsius"),
          "CPU temperature")
    gauge("timelapse_uptime_seconds", status.get("uptime_seconds"),
          "System uptime")

    # Capture
    today = status.get("today", {})
    gauge("timelapse_photos_captured_today", today.get("photos_captured"),
          "Photos captured today")
    gauge("timelapse_photos_expected_today", today.get("expected_photos"),
          "Expected photos for today")

    # Errors
    gauge("timelapse_errors_current", len(status.get("errors", [])),
          "Current error count")

    body = "\n".join(lines) + "\n"
    self.send_response(200)
    self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
    self.send_header("Content-Length", len(body))
    self.end_headers()
    self.wfile.write(body.encode())
```

### Prometheus Config (on your Prometheus server)

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'timelapse'
    scrape_interval: 60s
    static_configs:
      - targets: ['pi-zero-ip:8080']
```

### Grafana Dashboard

A pre-built dashboard JSON can be provided at `grafana/timelapse-dashboard.json` for import. Panels:
- Capture progress gauge (photos today / expected)
- Disk usage over time
- CPU temperature
- Daily photo counts
- Error timeline

This is maintained in the repo but **runs on your Grafana server**, not on the Pi.

### Configuration

```ini
# conf/timelapse.conf
[OBSERVABILITY]
prometheus_enabled = true
```

When `false`, the `/metrics` endpoint returns 404.

---

## Implementation Files

**Implemented:**

```
src/timelapse.cpp          # Writes /tmp/timelapse_status.json (C++)
src/timelapse.hpp          # Status tracking member variables
programs/metrics_server.py # Prometheus metrics HTTP server (Python stdlib only)
deploy/timelapse-metrics.service   # systemd service file
deploy/prometheus-scrape-config.yaml # Prometheus static target config for k3s
```

**Planned (not yet implemented):**

```
programs/status_writer.py      # Shared module: read/write /tmp/timelapse_status.json
programs/status_server.py      # Stdlib HTTP server (Layer 2)
programs/notifier.py           # Fire-and-forget notifications (Layer 3)
grafana/timelapse-dashboard.json  # Import into your Grafana (nice-to-have)
```

## Dependencies

**Metrics server (implemented):** Zero external dependencies (Python stdlib only).

```
Layer 1 (status file):     None — stdlib only
Layer 2 (status server):   None — stdlib only
Layer 3 (notifications):   requests (already installed for YouTube)
Nice-to-have (Prometheus): None — hand-formatted text, no pip package
```

## Resource Budget

| Component | CPU | RAM | Disk I/O | Network |
|-----------|-----|-----|----------|---------|
| Status file write | ~0 | ~0 | tmpfs (RAM) | None |
| Status server (idle) | 0% | ~5MB | None | None |
| Status server (request) | <1% for <100ms | ~5MB | One file read | One response |
| Notification (on error) | <1% for <1s | ~2MB | None | One HTTPS POST |
| Prometheus scrape | <1% for <100ms | ~0 | One file read | One response/60s |

---

## Implementation Order

### Phase 1: Status File
1. Create `status_writer.py` module
2. Integrate into Python programs (scheduler, manager, disk_cleanup)
3. Add JSON writing to C++ timelapse (after each capture, on status changes)
4. Verify with `cat /tmp/timelapse_status.json`

### Phase 2: Notifications
1. Create `notifier.py` module
2. Add `[NOTIFICATIONS]` config section
3. Wire into error paths in manager.py, disk_cleanup.py
4. Add C++ error → status file → notification bridge
5. Test with intentional failure

### Phase 3: Status Server
1. Create `status_server.py` with `/health`, `/status`, `/latest/*`
2. Create systemd service with resource limits
3. Add `[OBSERVABILITY]` config section
4. Test from browser/curl on local network

### Phase 4: Prometheus (Nice-to-Have)
1. Add `/metrics` endpoint to status server
2. Configure Prometheus to scrape
3. Import Grafana dashboard
4. No changes on the Pi beyond the one endpoint
