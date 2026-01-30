# Auto-Timelapse Project Overview

## Purpose

An autonomous timelapse camera system for Raspberry Pi that:
- Automatically calculates sunrise/sunset times for any location
- Captures photos throughout the day at optimal intervals
- Creates daily timelapse videos
- Backs up content to a NAS
- Manages disk space to run indefinitely without intervention

## Target Platform

Any Raspberry Pi with a camera module (Pi Zero through Pi 5), running Raspberry Pi OS.

## Key Features

### 1. Automatic Scheduling
- Queries sunrise-sunset.org API daily
- Calculates optimal photo interval to achieve target video length
- Configurable buffer time before/after sunrise/sunset
- No manual intervention needed for seasonal changes

### 2. Timelapse Capture (C++)
- High-performance capture loop with precise timing
- Uses `libcamera-still` (or configurable command)
- Creates MP4 video using OpenCV
- Logs CPU temperature during video creation

### 3. NAS Backup
- Automatic rsync to NAS after each day's capture
- Uses rsync daemon (no SSH keys required)
- Creates backup markers to track what's been synced
- Backs up both photos and videos

### 4. Disk Management
- Tiered cleanup strategy (photos first, then videos)
- Respects backup status (prefers deleting backed-up content)
- Emergency mode for critically full disks
- Minimum retention period (never deletes recent files)

### 5. YouTube Upload (Optional)
- Automatic upload of daily timelapses
- Configurable title, description, tags templates
- OAuth2 authentication

## Daily Workflow

```
00:00  scheduler.py      Generate tomorrow's schedule
00:01  disk_checker.py   Log disk space
02:00  timelapse         Start capture (waits for sunrise)
       ...               Captures photos all day
       ...               Creates video after sunset
06:00  disk_cleanup.py   Check disk, cleanup if needed
18:00  disk_cleanup.py   Check disk, cleanup if needed
23:00  manager.py        Backup to NAS, cleanup old files
```

## Project Structure

```
auto-timelapse/
├── src/                 # C++ source code
├── programs/            # Python scripts + compiled binary
├── conf/                # Configuration files
├── schedules/           # Generated daily schedules
├── pics/                # Photo directories (per day)
├── videos/              # Output videos
├── logs/                # All log files
├── build/               # Compiled objects
├── pm/                  # Project management docs
└── Makefile             # Build and installation
```

## Components Summary

| Component | Language | Purpose |
|-----------|----------|---------|
| timelapse | C++ | Core capture and video creation |
| scheduler.py | Python | Generate daily schedules from API |
| manager.py | Python | Backup to NAS, cleanup old files |
| disk_cleanup.py | Python | Autonomous disk space management |
| disk_checker.py | Python | Log disk usage for monitoring |
| set_up_cron.sh | Bash | Install all cron jobs |
| timelapse.conf | INI | Central configuration |

## Dependencies

- Raspberry Pi OS (Bookworm or later recommended)
- libcamera (for camera access)
- OpenCV 4 with FFMPEG support
- Python 3.9+
- rsync
- g++ compiler
- Network access (for API and NAS)
