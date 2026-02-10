# Setup and Installation Guide

## Prerequisites

### Hardware
- Raspberry Pi (any model with camera support)
- Camera module (Pi Camera v1/v2/v3 or HQ Camera)
- SD card (32GB+ recommended)
- Reliable power supply
- Network connection (WiFi or Ethernet)

### Software
- Raspberry Pi OS (Bookworm or later recommended)
- libcamera (included in modern Pi OS)
- Network access to sunrise-sunset.org API
- (Optional) NAS with rsync daemon for backups

## Step 1: System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install build tools
sudo apt install -y build-essential g++ make

# Install OpenCV (for video creation)
sudo apt install -y libopencv-dev

# Install Python dependencies
sudo apt install -y python3 python3-pip

# Python packages
pip3 install requests
```

## Step 2: Camera Setup

### Test Camera
```bash
# Check camera is detected
libcamera-hello --list-cameras

# Test capture
libcamera-still -o test.jpg
```

### Enable Camera (if needed)
```bash
sudo raspi-config
# Navigate to: Interface Options → Camera → Enable
# Reboot
```

## Step 3: Clone and Build

```bash
# Clone repository
cd ~
git clone https://github.com/yourusername/auto-timelapse.git
cd auto-timelapse

# Build everything (creates dirs, compiles, installs cron)
make all
```

### What `make all` does:
1. Creates directories: logs/, schedules/, pics/, videos/, build/
2. Makes Python scripts executable
3. Compiles C++ code to programs/timelapse
4. Installs cron jobs via set_up_cron.sh

## Step 4: Configuration

### Edit Configuration File
```bash
nano conf/timelapse.conf
```

### Required Settings

```ini
[DEVICE]
id = MyCam                    # Unique name for this camera

[SCHEDULER]
latitude = 51.5074            # Your location (London example)
longitude = -0.1278
timezone = Europe/London      # Your timezone
target_video_length_seconds = 30
target_fps = 25
buffer_minutes = 30           # Start before sunrise, end after sunset

[CAMERA]
capture_command = libcamera-still -n --immediate
resolution_width = 1920
resolution_height = 1080

[BACKUP]
backup_enabled = false        # Set true if you have NAS
nas_host = 192.168.1.100      # Your NAS IP
```

### Find Your Coordinates
- Google Maps: Right-click any location → coordinates shown
- Or use: https://www.latlong.net/

### Find Your Timezone
```bash
timedatectl list-timezones | grep -i london
```

## Step 5: NAS Setup (Optional)

### On Your NAS (Synology example)

1. Enable rsync service:
   - Control Panel → File Services → rsync → Enable rsync service

2. Create rsync module:
   - Edit `/etc/rsyncd.conf` or use NAS UI
   ```
   [timelapse]
   path = /volume1/timelapse
   read only = no
   ```

3. Create directory structure:
   ```
   /volume1/timelapse/
   └── {DeviceID}/          # Created automatically by rsync
   ```

### On Raspberry Pi

Update config:
```ini
[BACKUP]
backup_enabled = true
nas_host = 192.168.1.100
```

Test connection:
```bash
rsync -avh --dry-run test.txt rsync://192.168.1.100/timelapse/
```

## Step 6: Test Individual Components

### Test Scheduler
```bash
cd ~/auto-timelapse
python3 programs/scheduler.py

# Check output
cat schedules/$(date +%Y%m%d)_*_schedule.txt
```

### Test Capture (single photo)
```bash
./programs/timelapse --test  # If implemented
# Or manually:
libcamera-still -n --immediate -o test_photo.jpg
```

### Test Video Creation
```bash
# After a day of captures, or with test images:
./programs/timelapse
```

### Test Backup
```bash
python3 programs/manager.py
# Check logs/manager.log for results
```

### Test Disk Cleanup
```bash
python3 programs/disk_cleanup.py
# Check logs/disk_cleanup.log
```

## Step 7: Verify Cron Jobs

```bash
crontab -l
```

Expected output:
```
# Auto-timelapse cron jobs
0 0 * * * cd /home/pi/auto-timelapse && python3 programs/scheduler.py >> logs/scheduler.log 2>&1
1 0 * * * cd /home/pi/auto-timelapse && python3 programs/disk_checker.py >> logs/disk_check.log 2>&1
0 2 * * * cd /home/pi/auto-timelapse && ./programs/timelapse >> logs/todays_run.log 2>&1
0 6 * * * cd /home/pi/auto-timelapse && python3 programs/disk_cleanup.py >> logs/disk_cleanup.log 2>&1
0 18 * * * cd /home/pi/auto-timelapse && python3 programs/disk_cleanup.py >> logs/disk_cleanup.log 2>&1
0 23 * * * cd /home/pi/auto-timelapse && python3 programs/manager.py >> logs/manager.log 2>&1
```

## Step 8: First Run

### Generate First Schedule
```bash
python3 programs/scheduler.py
```

### Wait for Automatic Operation
The system will:
1. At 2 AM: Start timelapse capture
2. Throughout day: Capture photos
3. After sunset: Create video
4. At 11 PM: Backup to NAS
5. At midnight: Generate next day's schedule

### Or Run Manually
```bash
# Run timelapse now (will wait for start time from schedule)
./programs/timelapse

# Run with today's schedule, starting immediately (if you modify schedule)
```

## Troubleshooting

### Camera Not Found
```bash
# Check camera connection
vcgencmd get_camera
# Should show: supported=1 detected=1

# For Pi 5 / Bookworm:
libcamera-hello --list-cameras
```

### OpenCV Build Errors
```bash
# Ensure OpenCV is properly installed
pkg-config --modversion opencv4
# Should show version like 4.6.0
```

### Cron Jobs Not Running
```bash
# Check cron service
sudo systemctl status cron

# Check cron logs
grep CRON /var/log/syslog | tail -20
```

### NAS Connection Failed
```bash
# Test rsync manually
rsync -avh test.txt rsync://NAS_IP/timelapse/

# Check NAS rsync service is running
# Check firewall allows port 873
```

### Disk Filling Up
```bash
# Check disk usage
df -h

# Run cleanup manually
python3 programs/disk_cleanup.py

# Check what's using space
du -sh pics/* | sort -h
du -sh videos/* | sort -h
```

## Step 9: Prometheus Metrics (Optional)

The metrics server exposes operational data for Prometheus scraping. Zero pip
dependencies — uses only Python stdlib.

### Install the Metrics Service on the Pi

```bash
# Copy the systemd service file
sudo cp deploy/timelapse-metrics.service /etc/systemd/system/

# Reload systemd, enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable --now timelapse-metrics
```

### Verify the Metrics Server

```bash
# Check service is running
sudo systemctl status timelapse-metrics

# Test the endpoints
curl http://localhost:8080/metrics
curl http://localhost:8080/health

# From another machine on your network
curl http://PI_IP_ADDRESS:8080/metrics
```

You'll see output like:
```
# HELP timelapse_disk_usage_percent Disk usage percentage for the timelapse filesystem
# TYPE timelapse_disk_usage_percent gauge
timelapse_disk_usage_percent{device="Pi0Cam"} 68.5
# HELP timelapse_cpu_temperature_celsius CPU temperature in degrees Celsius
# TYPE timelapse_cpu_temperature_celsius gauge
timelapse_cpu_temperature_celsius{device="Pi0Cam"} 45.2
...
```

Note: Capture-related metrics (photos captured, last capture success, etc.) only
appear after the timelapse C++ binary has run at least once and written
`/tmp/timelapse_status.json`. System metrics (disk, CPU temp) are always available.

### Connect Prometheus (k3s)

The Prometheus config lives in the `jWorld-observability` repo. A static target
for the Pi has been added to `monitoring/prometheus/configmap.yaml`:

```yaml
- job_name: "timelapse"
  scrape_interval: 60s
  static_configs:
    - targets: ["PI_IP_ADDRESS:8080"]
      labels:
        device: "Pi0Cam"
```

Replace `PI_IP_ADDRESS` with the Pi's actual LAN IP, commit, and push. ArgoCD
auto-syncs the change to the cluster.

**Important:** Prometheus does not auto-reload when ConfigMap contents change. After
ArgoCD syncs, restart the Prometheus pod to pick up the new config:

```bash
kubectl scale deployment prometheus -n monitoring --replicas=0
# Wait a few seconds
kubectl scale deployment prometheus -n monitoring --replicas=1
```

### Verify Prometheus is Scraping

```bash
# Port-forward Prometheus UI
kubectl port-forward svc/prometheus -n monitoring 9090:9090

# Open http://localhost:9090/targets
# Look for the "timelapse" job — should show "UP"

# Query a metric
# In the Prometheus expression browser, try:
#   timelapse_disk_usage_percent
#   timelapse_photos_captured_today
```

### Troubleshooting Metrics

```bash
# Metrics server not starting?
sudo journalctl -u timelapse-metrics -f

# Port already in use?
sudo ss -tlnp | grep 8080

# Prometheus can't reach the Pi?
# Check firewall: sudo ufw allow 8080/tcp
# Check Pi is reachable: ping PI_IP_ADDRESS from a k3s node

# No capture metrics showing?
# The C++ binary hasn't run yet. Wait for the next capture run,
# or run it manually: ./programs/timelapse
# Then check: cat /tmp/timelapse_status.json
```

### Managing the Metrics Service

```bash
# View logs
sudo journalctl -u timelapse-metrics --since "1 hour ago"

# Restart after config changes
sudo systemctl restart timelapse-metrics

# Stop temporarily
sudo systemctl stop timelapse-metrics

# Disable (won't start on boot)
sudo systemctl disable timelapse-metrics
```

---

## Uninstallation

```bash
# Remove cron jobs
make clean

# Or manually:
crontab -e
# Remove all auto-timelapse lines

# Remove project files
rm -rf ~/auto-timelapse
```
