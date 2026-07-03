# Post-Mortem Addendum: Empty-Video Bug Re-diagnosed — July 2026

**System:** PiZeroCam (Raspberry Pi Zero W, 29GB SD card)
**Investigated:** 1–2 July 2026, during pre-departure testing, via SSH

This is a follow-up to [postmortem-march-2026.md](postmortem-march-2026.md), specifically
issue #4 ("March 19–23 video failures — unresolved"). That investigation could not pin
down a cause because the logs from those days had been overwritten. This time the logs
were intact, and a live recurrence was caught and tested directly. **This note does not
supersede the March postmortem — it's a different, independently-verified finding for
what was previously an open question.** Where the two disagree (see below), both are
documented as-is rather than picking a winner.

---

## What was found

### Recurrence of the empty-video bug (19–21 June, 1 July 2026)

Videos for 19, 20, 21 June and 1 July were all 44-byte empty MP4 containers — same
symptom as March. Unlike March, the source photos were intact (751/751, 381/381) and NAS
backup succeeded, so no data was lost. But the broken 44-byte videos were still marked
`.backed_up` and `.youtubed` and **were uploaded live to YouTube** (e.g.
`https://youtu.be/w2lDKqho6Kc` for 1 July) — `manager.py`/`youtube_upload.py` never
validate video file size/duration before treating it as a successful artifact.

### Working theory #1 (tested, and ruled out as sole cause): 02:58 cron collision

Initial hypothesis: the 02:58 AM `pkill -f programs/timelapse` cron job (added as part of
the March fix, to clear stale camera locks before the 3 AM capture) was killing the
previous night's video encode if it was still running past 02:58. Fixed by narrowing that
cron to `pkill -f libcamera-still` only. **This fix did not resolve the issue** — 1 July's
video still failed even with the corrected cron confirmed to have left the encode process
alone.

### Working theory #2 (confirmed via direct testing): failing SD card sector(s)

`dmesg`/`syslog` show repeated, recurring `I/O error, dev mmcblk0` on a small cluster of
sectors (`7632568`, `7632600`, `7632632` — each exactly 32 sectors / 16KB apart),
accompanied by `mmc0: timeout waiting for hardware interrupt`, spanning 1–2 July.

Direct test performed: manually re-ran video encoding twice using `ffmpeg` on the 1 July
photo set (all 381 individual photos verified independently readable via `md5sum`/`file` —
no per-file corruption). Both attempts died silently mid-encode with zero output, and both
coincided with fresh I/O errors on the same sector cluster in the kernel log. The second
attempt was run with swap disabled (see below) and still failed on a *different* nearby
sector — ruling out "it's purely the swap file" as the complete explanation. One test also
caused a full SSH/network stall for several seconds while the SD controller was retrying,
indicating the fault affects the whole system's I/O, not just file reads for this one
process.

**Conclusion: a genuinely failing region of the physical SD card**, not a one-off, not
OOM (memory was never critically low: 96MB free at the time), and not the March apt-
upgrade issue recurring (confirmed: `/var/log/apt/history.log` and `dpkg.log` show zero
package activity since 25 March 2026 — no auto-upgrades are even configured on this
device).

### Discussion: why this SD card may be wearing unevenly

Two usage patterns on this device concentrate writes on the same physical region of flash
rather than spreading them across the card, which is a known way to prematurely wear
consumer (non-industrial) SD cards:

1. **Swap file** (`/var/swap`, 256MB) — allocated once, fixed block mapping for its
   lifetime. Every swap in/out cycle rewrites the same physical cells. Was sitting at
   119MB/256MB used under normal idle load on a 365MB-RAM Pi Zero, before this
   investigation.
2. **Capture/cleanup churn** — `disk_cleanup.py` deletes ~1 day of photos as fast as
   ~1 day of new photos is written, holding disk usage steady around 32–36% for months.
   On a mostly-empty, slowly-churning filesystem like this, the free-block allocator tends
   to reuse similar physical regions repeatedly rather than spreading writes across the
   full 29GB.

Both are plausible contributors to the same physical region degrading; this wasn't
proven conclusively (no long-term wear telemetry exists — see gap below), but the
mechanism is well-documented for this class of embedded/logging device.

---

## Gap identified: no memory/wear telemetry

The Prometheus exporter (`programs/metrics_server.py`, added Feb 2026) tracks CPU temp,
disk usage %, photo counts, and process/video status — but never tracked RAM or swap
usage, and nothing on-device retains history (it's scrape-only, no local time-series
store). There is no way to look back and confirm memory pressure at the moment of any
past failure.

---

## Immediate actions taken (1–2 July 2026)

1. Fixed `boot_scheduler.sh` — a separate, unrelated bug (`os.chdir('')` with an empty
   string) was crashing schedule generation on every boot, which also explains an earlier
   isolated capture failure on 18 June (`Error: Could not find today's schedule file`).
2. Narrowed the 02:58 AM cron job (kept, since it's still useful for stale
   `libcamera-still` locks — just no longer a plausible cause of this specific bug).
3. Swap disabled as a precaution pending hardware replacement.
4. Camera refocused for far-distance subject (unrelated maintenance, done same session).

## Recommended next steps

- Replace the SD card before the unattended month-long run (in progress as of this
  writing).
- See separate planning note for broader architecture changes under consideration
  (offloading video compilation off-device, moving swap/writes to reduce SD wear, etc).
