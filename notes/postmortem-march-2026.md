# Post-Mortem: Timelapse Pipeline Outage — March 2026

**System:** PiZeroCam (Raspberry Pi Zero W, 29GB SD card)
**Outage period:** 19 March 2026 – 16 June 2026 (restarted)
**Investigated:** 16–17 June 2026 using SSH + NAS rsync logs

---

## What happened

The pipeline stopped producing videos on 19 March 2026. Photos continued to be captured and backed up until late May, then the system went silent entirely. The SD card was suspected but is not the cause.

---

## Timeline

| Date | Event |
|------|-------|
| 18 Mar 2026 | Last good video (359MB, `20260318_Pi0Cam_timelapse.mp4`) |
| 19–23 Mar 2026 | Videos produced are **44 bytes** — empty MP4 container, no frames written |
| 24 Mar 2026 12:50 PM | **`apt upgrade` ran mid-capture session**, updating GStreamer, libpng, libvpx, OpenSSL, Python. Capture log shows last photo at 10:44 AM — the upgrade killed the active timelapse process |
| 25 Mar 2026+ | NAS photo directories are 4KB (empty) — rsync backup broken, likely same upgrade broke Python/SSL used by manager.py |
| 1 May 2026+ | Scheduler logs show DNS failures — can no longer reach sunrise-sunset API |
| 22 May 2026+ | Manager logs show "Network is unreachable" for NAS rsync (Pi losing WiFi) |
| 26 May 2026 | Last local capture (mid-day, Pi was then unplugged) |
| 16 Jun 2026 | Pi plugged back in. Detective work begins. |

---

## Root causes

### 1. `apt upgrade` ran mid-capture (24 March 2026) — primary cause of full outage

An `apt upgrade` ran at 12:50 PM while the timelapse binary was actively capturing photos. It updated libraries the compiled C++ binary links against:

- `libgstreamer-plugins-base1.0-0`, `gstreamer1.0-plugins-good`, `gstreamer1.0-x` — used by OpenCV's video backend
- `libpng16-16`, `libvpx6` — used by OpenCV image/video encoding
- `libssl1.1`, `ca-certificates` — used by Python rsync/urllib for NAS backup
- `python3.9` and `python-apt` — used by all pipeline Python scripts

After this upgrade, the compiled binary was linked against old library versions no longer present. Result: video encoding silently failed, then camera access broke entirely.

**Fix:** Recompile the binary (`make build`) against current library versions.

### 2. WiFi power management enabled — caused intermittent network loss

The Pi Zero's WiFi was running with power management ON (`Power Management: on`). This causes the adapter to sleep between packets, eventually dropping the connection entirely. This explains:
- NAS rsync "Network is unreachable" errors from May 22
- DNS resolution failures from May 1

**Fix:** `sudo iwconfig wlan0 power off` added to `/etc/rc.local` (persists across reboots).

### 3. Camera lock accumulation — secondary cause of capture failures

When the timelapse binary crashes or is killed mid-run, it leaves a stale `libcamera-still` process holding the camera lock. The next day's run then fails with:

```
ERROR: *** failed to acquire camera /base/soc/i2c0mux/i2c@1/imx219@10 ***
Pipeline handler in use by another process
```

Over multiple days these accumulate. Rebooting clears them, but there was no automatic recovery.

**Fix:** Add a cron job at 2:58 AM to kill stale processes before the 3 AM timelapse start:
```
58 2 * * * pkill -f libcamera-still; pkill -f programs/timelapse; exit 0
```

### 4. March 19–23 video failures (44-byte files) — unresolved

Videos produced empty MP4 containers for 5 consecutive days before the apt upgrade. Photos for those days were backed up normally (full NAS directories), so capture was working. Video creation failed immediately — the VideoWriter opened but wrote no frames.

Possible causes (logs from those days were overwritten by subsequent runs):
- OOM kill during OpenCV video encoding — spring days are longer (more photos = more RAM needed for encoding)
- Codec backend issue pre-dating the apt upgrade
- One-time crash on March 19 that cascaded (stale process blocking subsequent runs)

This was not the SD card.

---

## What was NOT the cause

- **SD card corruption** — disk was 32% used when investigated, filesystem healthy
- **Disk space** — logs show 68–82% usage throughout March, cleanup was functioning correctly, 5–9GB free at time of video creation each evening
- **Prometheus/observability** — added 10 February 2026, when everything was working fine
- **Memory card** — confirmed healthy after external disk check tool

---

## Fixes applied (June 2026)

1. WiFi power management disabled persistently via `/etc/rc.local`
2. Binary recompiled against current libraries (`make build`)
3. Camera lock cleanup cron added at 2:58 AM
4. Pi rebooted and confirmed: network up, camera detected, disk healthy

---

## Lessons

- Never run `apt upgrade` unattended on a Pi that runs a compiled binary against system libs — either pin packages or add a post-upgrade recompile hook
- The disk space monitoring (`disk_check.log`) was valuable for ruling out false causes
- The NAS backup timestamps gave precise failure dates without needing the Pi itself
- WiFi power management should be disabled at first boot setup, not as an afterthought
