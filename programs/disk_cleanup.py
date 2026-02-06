#!/usr/bin/env python3
"""
Disk-based cleanup script for auto-timelapse.

Runs independently of manager.py to ensure cleanup happens even if backups fail.
Uses disk usage thresholds to trigger cleanup, with tiered deletion:
1. Delete old photo directories first (oldest first, must have .backed_up marker)
2. Delete old videos only as lastdi resort (oldest first, must have .backed_up marker)

Safety: Never deletes anything younger than MIN_RETENTION_DAYS.
"""

import shutil
import configparser
from datetime import datetime, timedelta
from pathlib import Path
import sys
import logging

# Define the base path for the script location (i.e., programs/)
SCRIPT_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_PATH.parent
LOGS_DIR = PROJECT_ROOT / "logs"
PICS_DIR = PROJECT_ROOT / "pics"
VIDEOS_DIR = PROJECT_ROOT / "videos"
CONF_DIR = PROJECT_ROOT / "conf"

# Marker file name created by manager.py after successful backup
BACKUP_MARKER = ".backed_up"

# --- Logger Setup ---
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE_PATH = LOGS_DIR / "disk_cleanup.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)


def load_config():
    """Load configuration from timelapse.conf."""
    config_file = CONF_DIR / "timelapse.conf"
    config = configparser.ConfigParser()

    # Defaults for disk cleanup
    defaults = {
        'start_cleanup_percent': 80,
        'target_percent': 70,
        'emergency_percent': 90,
        'emergency_target_percent': 80,
        'min_retention_days': 7,
    }

    if config_file.exists():
        config.read(config_file)

    # Return config values with defaults
    return {
        'start_cleanup_percent': config.getint('DISK_CLEANUP', 'start_cleanup_percent', fallback=defaults['start_cleanup_percent']),
        'target_percent': config.getint('DISK_CLEANUP', 'target_percent', fallback=defaults['target_percent']),
        'emergency_percent': config.getint('DISK_CLEANUP', 'emergency_percent', fallback=defaults['emergency_percent']),
        'emergency_target_percent': config.getint('DISK_CLEANUP', 'emergency_target_percent', fallback=defaults['emergency_target_percent']),
        'min_retention_days': config.getint('DISK_CLEANUP', 'min_retention_days', fallback=defaults['min_retention_days']),
    }


def get_disk_usage_percent(path="/"):
    """Get current disk usage percentage for the given path.

    Uses the same calculation as 'df': used / (used + free)
    This accounts for reserved blocks and matches what users see.
    """
    usage = shutil.disk_usage(path)
    # Match df calculation: used / (used + available), not used / total
    # This accounts for reserved blocks on ext4 filesystems
    percent = (usage.used / (usage.used + usage.free)) * 100
    return percent


def extract_date_from_name(name, patterns=None):
    """
    Extract date from filename/dirname.
    Tries multiple patterns to handle different naming conventions.
    """
    if patterns is None:
        patterns = ['%Y%m%d', '%Y-%m-%d']

    # Try to find a date-like segment in the name
    # Common formats: 20251207, 2025-12-07, timelapse_20251207_...
    parts = name.replace('-', '_').split('_')

    for part in parts:
        for pattern in patterns:
            try:
                return datetime.strptime(part, pattern)
            except ValueError:
                continue

    return None


def get_photo_directories_sorted_by_age():
    """
    Get all photo directories sorted by date (oldest first).
    Returns list of (path, date, has_backup_marker) tuples.
    """
    directories = []

    if not PICS_DIR.exists():
        return directories

    for item_path in PICS_DIR.iterdir():
        if not item_path.is_dir():
            continue

        item_date = extract_date_from_name(item_path.name)
        if item_date is None:
            logging.warning(f"Could not extract date from directory: {item_path.name}")
            continue

        has_marker = (item_path / BACKUP_MARKER).exists()
        directories.append((item_path, item_date, has_marker))

    # Sort by date, oldest first
    directories.sort(key=lambda x: x[1])
    return directories


def get_video_files_sorted_by_age():
    """
    Get all video files sorted by date (oldest first).
    Returns list of (path, date, has_backup_marker) tuples.
    """
    videos = []

    if not VIDEOS_DIR.exists():
        return videos

    for item_path in VIDEOS_DIR.iterdir():
        if not item_path.is_file():
            continue
        if not item_path.suffix.lower() == '.mp4':
            continue

        item_date = extract_date_from_name(item_path.stem)
        if item_date is None:
            logging.warning(f"Could not extract date from video: {item_path.name}")
            continue

        # Check for marker file: {video_name}.backed_up
        marker_path = VIDEOS_DIR / f"{item_path.name}.backed_up"
        has_marker = marker_path.exists()
        videos.append((item_path, item_date, has_marker))

    # Sort by date, oldest first
    videos.sort(key=lambda x: x[1])
    return videos


def cleanup_photos(target_percent, min_retention_days, require_backup_marker=True):
    """
    Delete old photo directories until disk usage is below target.

    Args:
        target_percent: Stop deleting when disk usage falls below this
        min_retention_days: Never delete directories younger than this
        require_backup_marker: If True, only delete backed-up directories.
                               If False, delete even unbackedup directories (data loss fallback).

    Returns number of directories deleted.
    """
    cutoff_date = datetime.now() - timedelta(days=min_retention_days)
    deleted_count = 0

    directories = get_photo_directories_sorted_by_age()

    for dir_path, dir_date, has_marker in directories:
        current_usage = get_disk_usage_percent()

        if current_usage <= target_percent:
            logging.info(f"Disk usage {current_usage:.1f}% is below target {target_percent}%. Stopping photo cleanup.")
            break

        # Safety check: never delete recent directories
        if dir_date >= cutoff_date:
            logging.debug(f"Skipping {dir_path.name} - younger than {min_retention_days} days")
            continue

        # Check backup marker requirement
        if require_backup_marker and not has_marker:
            logging.warning(f"Skipping {dir_path.name} - no backup marker (not yet backed up)")
            continue

        # Delete the directory
        try:
            if not has_marker:
                logging.warning(f"DELETING UNBACKEDUP directory to free disk space: {dir_path.name}")
            shutil.rmtree(dir_path)
            deleted_count += 1
            logging.info(f"Deleted photo directory: {dir_path.name} (date: {dir_date.strftime('%Y-%m-%d')})")
        except OSError as e:
            logging.error(f"Failed to delete {dir_path}: {e}")

    return deleted_count


def cleanup_videos(target_percent, min_retention_days, require_backup_marker=True):
    """
    Delete old video files until disk usage is below target.

    Args:
        target_percent: Stop deleting when disk usage falls below this
        min_retention_days: Never delete videos younger than this
        require_backup_marker: If True, only delete backed-up videos.
                               If False, delete even unbackedup videos (data loss fallback).

    Returns number of videos deleted.
    """
    cutoff_date = datetime.now() - timedelta(days=min_retention_days)
    deleted_count = 0

    videos = get_video_files_sorted_by_age()

    for video_path, video_date, has_marker in videos:
        current_usage = get_disk_usage_percent()

        if current_usage <= target_percent:
            logging.info(f"Disk usage {current_usage:.1f}% is below target {target_percent}%. Stopping video cleanup.")
            break

        # Safety check: never delete recent videos
        if video_date >= cutoff_date:
            logging.debug(f"Skipping {video_path.name} - younger than {min_retention_days} days")
            continue

        # Check backup marker requirement
        if require_backup_marker and not has_marker:
            logging.warning(f"Skipping {video_path.name} - no backup marker (not yet backed up)")
            continue

        # Delete the video
        try:
            if not has_marker:
                logging.warning(f"DELETING UNBACKEDUP video to free disk space: {video_path.name}")
            video_path.unlink()
            # Also remove the marker file if it exists
            marker_path = VIDEOS_DIR / f"{video_path.name}.backed_up"
            if marker_path.exists():
                marker_path.unlink()
            deleted_count += 1
            logging.info(f"Deleted video: {video_path.name} (date: {video_date.strftime('%Y-%m-%d')})")
        except OSError as e:
            logging.error(f"Failed to delete {video_path}: {e}")

    return deleted_count


def main():
    """Main cleanup logic with tiered approach."""
    logging.info("=== Disk cleanup started ===")

    config = load_config()

    start_percent = config['start_cleanup_percent']
    target_percent = config['target_percent']
    emergency_percent = config['emergency_percent']
    emergency_target = config['emergency_target_percent']
    min_days = config['min_retention_days']

    current_usage = get_disk_usage_percent()
    logging.info(f"Current disk usage: {current_usage:.1f}%")
    logging.info(f"Thresholds - Start: {start_percent}%, Target: {target_percent}%, Emergency: {emergency_percent}%")
    logging.info(f"Minimum retention: {min_days} days")

    # Check if cleanup is needed
    if current_usage < start_percent:
        logging.info(f"Disk usage {current_usage:.1f}% is below threshold {start_percent}%. No cleanup needed.")
        logging.info("=== Disk cleanup finished ===")
        return

    # Tier 1: Clean up backed-up photos first
    logging.info(f"Disk usage {current_usage:.1f}% exceeds {start_percent}%. Starting photo cleanup...")
    photos_deleted = cleanup_photos(target_percent, min_days, require_backup_marker=True)
    logging.info(f"Photo cleanup (backed-up only) complete. Deleted {photos_deleted} directories.")

    # Tier 2: Emergency - clean up backed-up videos
    current_usage = get_disk_usage_percent()
    if current_usage >= emergency_percent:
        logging.warning(f"EMERGENCY: Disk usage {current_usage:.1f}% exceeds {emergency_percent}%. Starting video cleanup...")
        videos_deleted = cleanup_videos(emergency_target, min_days, require_backup_marker=True)
        logging.warning(f"Video cleanup (backed-up only) complete. Deleted {videos_deleted} videos.")

    # Final check - we intentionally do NOT delete unbacked items
    # In doomsday scenario, disk fills up preserving all data as a forensic record
    final_usage = get_disk_usage_percent()
    if final_usage >= start_percent:
        logging.warning(f"Disk usage at {final_usage:.1f}% - only backed-up items can be deleted.")
        logging.warning("Unbacked items preserved. Disk may fill up if backups continue to fail.")

    logging.info(f"Final disk usage: {final_usage:.1f}%")
    logging.info("=== Disk cleanup finished ===")


if __name__ == "__main__":
    main()
