# Configuration Reference

All configuration is in `conf/timelapse.conf` (INI format).

## [DEVICE]

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `id` | string | `Pi0Cam` | Unique identifier for this camera. Used in all filenames and NAS paths. |

**Example:**
```ini
[DEVICE]
id = GardenCam
```

---

## [SCHEDULER]

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `latitude` | float | `60.1699` | Location latitude for sunrise/sunset API |
| `longitude` | float | `24.9384` | Location longitude for sunrise/sunset API |
| `timezone` | string | `Europe/Helsinki` | Timezone for time calculations |
| `target_video_length_seconds` | int | `30` | Desired length of output video |
| `target_fps` | int | `25` | Frames per second in output video |
| `min_interval_seconds` | int | `10` | Minimum seconds between photos |
| `max_interval_seconds` | int | `120` | Maximum seconds between photos |
| `buffer_minutes` | int | `45` | Minutes before sunrise / after sunset to capture |

**How interval is calculated:**
```
daylight_seconds = (sunset + buffer) - (sunrise - buffer)
target_photos = target_video_length * target_fps
interval = daylight_seconds / target_photos
interval = clamp(interval, min_interval, max_interval)
```

**Example:**
```ini
[SCHEDULER]
latitude = 51.5074
longitude = -0.1278
timezone = Europe/London
target_video_length_seconds = 45
target_fps = 30
min_interval_seconds = 15
max_interval_seconds = 90
buffer_minutes = 30
```

---

## [CAMERA]

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `capture_command` | string | `libcamera-still -n --immediate` | Command to capture a photo |
| `resolution_width` | int | `1920` | Image width in pixels |
| `resolution_height` | int | `1080` | Image height in pixels |
| `image_format` | string | `jpg` | Output image format |

**Capture Command:**
The C++ program appends `-o {filename}` to this command. Examples:

```ini
# Raspberry Pi Camera (libcamera)
capture_command = libcamera-still -n --immediate

# With specific exposure
capture_command = libcamera-still -n --immediate --shutter 10000

# USB webcam
capture_command = fswebcam -r 1920x1080 --no-banner

# Custom script
capture_command = /home/pi/custom_capture.sh
```

---

## [BACKUP]

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `nas_host` | string | `your-nas-ip` | NAS IP address or hostname |
| `nas_user` | string | `your-username` | (Not used with rsync daemon) |
| `nas_path` | string | `/volume1/auto-timelapse/` | Base path on NAS |
| `rsync_options` | string | `-avz --progress` | Additional rsync flags |
| `backup_enabled` | bool | `true` | Enable/disable NAS backup |
| `delete_after_backup` | bool | `false` | Delete photos immediately after backup |

**Rsync URL format:**
```
rsync://{nas_host}/timelapse/{device_id}/{folder_or_file}
```

**Example:**
```ini
[BACKUP]
nas_host = 192.168.1.100
backup_enabled = true
delete_after_backup = false
```

---

## [CLEANUP]

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `keep_days` | int | `5` | Keep photos for this many days locally |
| `keep_videos` | int | `5` | Keep videos for this many days locally |
| `cleanup_enabled` | bool | `true` | Enable retention-based cleanup in manager.py |

**Note:** This is the age-based cleanup in manager.py. The disk-based cleanup in disk_cleanup.py uses different settings (see below).

**Example:**
```ini
[CLEANUP]
keep_days = 14
keep_videos = 30
cleanup_enabled = true
```

---

## [DISK_CLEANUP]

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `start_cleanup_percent` | int | `80` | Start deleting when disk exceeds this % |
| `target_percent` | int | `70` | Target % to reach after normal cleanup |
| `emergency_percent` | int | `90` | Emergency threshold for video deletion |
| `emergency_target_percent` | int | `80` | Target % to reach after emergency cleanup |
| `min_retention_days` | int | `7` | Never delete files younger than this |

**Cleanup tiers:**
1. Disk > 80%: Delete backed-up photos until < 70%
2. Still > 80%: Delete unbackedup photos until < 70%
3. Disk > 90%: Delete backed-up videos until < 80%
4. Still > 90%: Delete unbackedup videos until < 80%

**Example:**
```ini
[DISK_CLEANUP]
start_cleanup_percent = 75
target_percent = 60
emergency_percent = 85
emergency_target_percent = 70
min_retention_days = 5
```

---

## [YOUTUBE]

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `upload_enabled` | bool | `false` | Enable YouTube upload |
| `client_secrets_file` | string | `client_secrets.json` | OAuth client secrets file |
| `credentials_file` | string | `youtube_credentials.json` | Stored OAuth credentials |
| `default_title` | string | `Daily Timelapse {device_id} {date}` | Video title template |
| `default_description` | string | (see below) | Video description template |
| `default_tags` | string | `timelapse,raspberry pi,automated,daily` | Comma-separated tags |
| `default_privacy` | string | `public` | `public`, `private`, or `unlisted` |

**Template variables:**
- `{device_id}` - From [DEVICE] id
- `{date}` - YYYY-MM-DD format
- `{sunrise}` - Sunrise time from schedule
- `{sunset}` - Sunset time from schedule

**Example:**
```ini
[YOUTUBE]
upload_enabled = true
client_secrets_file = /home/pi/.youtube/client_secrets.json
credentials_file = /home/pi/.youtube/credentials.json
default_title = Garden Timelapse - {date}
default_description = Daily timelapse from the garden. Sunrise: {sunrise}, Sunset: {sunset}
default_tags = timelapse,garden,nature,daily
default_privacy = unlisted
```

---

## [METRICS] *(implemented)*

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | `true` | Enable the Prometheus metrics server |
| `port` | int | `8080` | HTTP port for the metrics endpoint |
| `bind` | string | `0.0.0.0` | Bind address (`0.0.0.0` for all interfaces, `127.0.0.1` for local only) |

The metrics server runs as a systemd service and exposes a `/metrics` endpoint
in Prometheus text exposition format. See `deploy/timelapse-metrics.service`.

**Example:**

```ini
[METRICS]
enabled = true
port = 8080
bind = 0.0.0.0
```

---

## [OBSERVABILITY] *(planned)*

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `status_server_enabled` | bool | `false` | Enable the lightweight HTTP status server |
| `status_server_port` | int | `8080` | Port for the status server |
| `status_server_bind` | string | `0.0.0.0` | Bind address (`0.0.0.0` for network, `127.0.0.1` for local only) |
| `prometheus_enabled` | bool | `false` | Expose `/metrics` endpoint in Prometheus text format |

**Note:** The status file (`/tmp/timelapse_status.json`) is always written regardless of these settings. The server and Prometheus endpoint are optional layers on top.

**Example:**
```ini
[OBSERVABILITY]
status_server_enabled = true
status_server_port = 8080
status_server_bind = 0.0.0.0
prometheus_enabled = true
```

---

## [NOTIFICATIONS] *(planned)*

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | `false` | Enable error notifications |
| `min_level` | string | `WARNING` | Minimum level to notify: `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `telegram_enabled` | bool | `false` | Send notifications via Telegram |
| `telegram_bot_token` | string | | Telegram bot token from @BotFather |
| `telegram_chat_id` | string | | Telegram chat ID to send messages to |
| `discord_enabled` | bool | `false` | Send notifications via Discord |
| `discord_webhook_url` | string | | Discord webhook URL |
| `webhook_enabled` | bool | `false` | Send notifications via generic webhook |
| `webhook_url` | string | | Webhook URL (Home Assistant, Slack, etc.) |
| `daily_summary_enabled` | bool | `false` | Send daily summary at end of manager.py run |

**Example:**
```ini
[NOTIFICATIONS]
enabled = true
min_level = WARNING
telegram_enabled = true
telegram_bot_token = 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
telegram_chat_id = -1001234567890
daily_summary_enabled = true
```

---

## [PATHS]

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `timelapse_dir` | string | `.` | Project root directory |

Generally not needed as paths are relative to project root.

---

## Complete Example Configuration

```ini
[DEVICE]
id = GardenCam

[SCHEDULER]
latitude = 51.5074
longitude = -0.1278
timezone = Europe/London
target_video_length_seconds = 45
target_fps = 30
min_interval_seconds = 15
max_interval_seconds = 90
buffer_minutes = 30

[CAMERA]
capture_command = libcamera-still -n --immediate
resolution_width = 1920
resolution_height = 1080
image_format = jpg

[BACKUP]
nas_host = 192.168.1.100
backup_enabled = true
delete_after_backup = false

[CLEANUP]
keep_days = 14
keep_videos = 30
cleanup_enabled = true

[DISK_CLEANUP]
start_cleanup_percent = 80
target_percent = 70
emergency_percent = 90
emergency_target_percent = 80
min_retention_days = 7

[METRICS]
enabled = true
port = 8080
bind = 0.0.0.0

[YOUTUBE]
upload_enabled = false

[OBSERVABILITY]
status_server_enabled = false
status_server_port = 8080
status_server_bind = 0.0.0.0
prometheus_enabled = false

[NOTIFICATIONS]
enabled = false
min_level = WARNING
telegram_enabled = false
telegram_bot_token =
telegram_chat_id =
discord_enabled = false
discord_webhook_url =
webhook_enabled = false
webhook_url =
daily_summary_enabled = false

[PATHS]
timelapse_dir = .
```
