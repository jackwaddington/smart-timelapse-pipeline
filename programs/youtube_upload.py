#!/usr/bin/env python3
"""
YouTube Video Upload Script

Uploads timelapse videos to YouTube with configurable metadata.

Usage:
    python3 youtube_upload.py                     # Upload yesterday's video
    python3 youtube_upload.py --date 2026-01-28   # Upload specific date
    python3 youtube_upload.py --all               # Upload all un-uploaded videos
    python3 youtube_upload.py --file video.mp4   # Upload specific file
    python3 youtube_upload.py --dry-run          # Show what would be uploaded
"""

import sys
import json
import argparse
import logging
import configparser
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
SCRIPT_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_PATH.parent
CONF_DIR = PROJECT_ROOT / "conf"
VIDEOS_DIR = PROJECT_ROOT / "videos"
SCHEDULES_DIR = PROJECT_ROOT / "schedules"
LOGS_DIR = PROJECT_ROOT / "logs"

# Credentials
CLIENT_SECRETS_FILE = CONF_DIR / "client_secrets.json"
CREDENTIALS_FILE = CONF_DIR / "youtube_credentials.json"
CONFIG_FILE = CONF_DIR / "timelapse.conf"

# Setup logging
LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "youtube_upload.log"),
        logging.StreamHandler(sys.stdout)
    ]
)


def load_config():
    """Load configuration from timelapse.conf."""
    config = configparser.ConfigParser()

    if CONFIG_FILE.exists():
        config.read(CONFIG_FILE)

    return {
        'device_id': config.get('DEVICE', 'id', fallback='Pi0Cam'),
        'upload_enabled': config.getboolean('YOUTUBE', 'upload_enabled', fallback=True),
        'title_template': config.get('YOUTUBE', 'default_title',
                                     fallback='{device_id} Timelapse - {date}'),
        'description_template': config.get('YOUTUBE', 'default_description',
                                           fallback='Automated daily timelapse from {device_id}.\n\nSunrise: {sunrise}\nSunset: {sunset}\n\nCaptured with Raspberry Pi'),
        'tags': config.get('YOUTUBE', 'default_tags',
                          fallback='timelapse,raspberry pi,automated,daily').split(','),
        'category_id': config.get('YOUTUBE', 'default_category', fallback='22'),
        'privacy': config.get('YOUTUBE', 'default_privacy', fallback='unlisted'),
        'playlist_id': config.get('YOUTUBE', 'playlist_id', fallback=''),
    }


def load_credentials():
    """Load YouTube credentials from file."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not CREDENTIALS_FILE.exists():
        logging.error(f"Credentials not found: {CREDENTIALS_FILE}")
        logging.error("Run: python3 youtube_auth.py --headless")
        return None

    with open(CREDENTIALS_FILE, 'r') as f:
        creds_data = json.load(f)

    credentials = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data['refresh_token'],
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )

    # Refresh if expired
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            # Save refreshed credentials
            creds_data['token'] = credentials.token
            with open(CREDENTIALS_FILE, 'w') as f:
                json.dump(creds_data, f, indent=2)
            logging.info("Credentials refreshed successfully")
        except Exception as e:
            logging.error(f"Failed to refresh credentials: {e}")
            return None

    return credentials


def load_schedule_data(date_str, device_id):
    """Load schedule data for a specific date."""
    clean_date = date_str.replace('-', '')
    schedule_file = SCHEDULES_DIR / f"{clean_date}_{device_id}_schedule.txt"

    data = {
        'date': date_str,
        'date_readable': datetime.strptime(date_str, '%Y-%m-%d').strftime('%B %d, %Y'),
        'device_id': device_id,
        'sunrise': 'N/A',
        'sunset': 'N/A',
        'photo_count': 'N/A',
        'video_duration': 'N/A',
    }

    if schedule_file.exists():
        try:
            with open(schedule_file, 'r') as f:
                for line in f:
                    if line.startswith('Sunrise:'):
                        data['sunrise'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Sunset:'):
                        data['sunset'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Expected Photos:'):
                        data['photo_count'] = line.split(':', 1)[1].strip()
        except Exception as e:
            logging.warning(f"Could not read schedule file: {e}")

    return data


def format_template(template, data):
    """Format a template string with data."""
    result = template
    for key, value in data.items():
        result = result.replace('{' + key + '}', str(value))
    return result


def get_video_for_date(date_str, device_id):
    """Find video file for a specific date."""
    clean_date = date_str.replace('-', '')
    video_file = VIDEOS_DIR / f"{clean_date}_{device_id}_timelapse.mp4"

    if video_file.exists():
        return video_file
    return None


def is_already_uploaded(video_file):
    """Check if video has already been uploaded."""
    marker_file = video_file.parent / f"{video_file.name}.youtubed"
    return marker_file.exists()


def get_all_unuploaded_videos(device_id):
    """Get list of all videos that haven't been uploaded yet."""
    videos = []

    for video_file in VIDEOS_DIR.glob(f"*_{device_id}_timelapse.mp4"):
        if not is_already_uploaded(video_file):
            # Extract date from filename
            date_part = video_file.name.split('_')[0]
            try:
                video_date = datetime.strptime(date_part, '%Y%m%d')
                date_str = video_date.strftime('%Y-%m-%d')
                videos.append((video_file, date_str))
            except ValueError:
                logging.warning(f"Could not parse date from: {video_file.name}")

    # Sort by date, oldest first
    videos.sort(key=lambda x: x[1])
    return videos


def upload_video(video_file, schedule_data, config, dry_run=False):
    """
    Upload a video to YouTube.

    Returns the YouTube video URL on success, None on failure.
    """
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    # Prepare metadata
    title = format_template(config['title_template'], schedule_data)[:100]  # YouTube limit
    description = format_template(config['description_template'], schedule_data)[:5000]
    tags = [format_template(tag.strip(), schedule_data) for tag in config['tags']]

    logging.info(f"Uploading: {video_file.name}")
    logging.info(f"  Title: {title}")
    logging.info(f"  Privacy: {config['privacy']}")

    if dry_run:
        logging.info("  [DRY RUN] Would upload this video")
        return "https://youtu.be/DRYRUN"

    # Load credentials
    credentials = load_credentials()
    if not credentials:
        return None

    try:
        youtube = build('youtube', 'v3', credentials=credentials)

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': config['category_id']
            },
            'status': {
                'privacyStatus': config['privacy'],
                'selfDeclaredMadeForKids': False
            }
        }

        # Create upload request
        media = MediaFileUpload(
            str(video_file),
            mimetype='video/mp4',
            resumable=True,
            chunksize=1024*1024  # 1MB chunks
        )

        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )

        # Execute upload with progress
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logging.info(f"  Upload progress: {progress}%")

        video_id = response['id']
        video_url = f"https://youtu.be/{video_id}"

        logging.info(f"  Upload complete: {video_url}")

        # Create marker file
        marker_file = video_file.parent / f"{video_file.name}.youtubed"
        marker_file.write_text(video_url)
        logging.info(f"  Created marker: {marker_file.name}")

        # Add to playlist if configured
        if config['playlist_id']:
            try:
                youtube.playlistItems().insert(
                    part='snippet',
                    body={
                        'snippet': {
                            'playlistId': config['playlist_id'],
                            'resourceId': {
                                'kind': 'youtube#video',
                                'videoId': video_id
                            }
                        }
                    }
                ).execute()
                logging.info(f"  Added to playlist: {config['playlist_id']}")
            except HttpError as e:
                logging.warning(f"  Could not add to playlist: {e}")

        return video_url

    except HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in str(e):
            logging.error("YouTube API quota exceeded. Try again tomorrow.")
        else:
            logging.error(f"YouTube API error: {e}")
        return None
    except Exception as e:
        logging.error(f"Upload failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Upload timelapse videos to YouTube')
    parser.add_argument('--date', type=str, help='Date to upload (YYYY-MM-DD)')
    parser.add_argument('--file', type=str, help='Specific video file to upload')
    parser.add_argument('--all', action='store_true', help='Upload all un-uploaded videos')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be uploaded')
    args = parser.parse_args()

    # Check dependencies
    try:
        from googleapiclient.discovery import build
    except ImportError:
        logging.error("Missing dependencies. Install with:")
        logging.error("  pip3 install google-api-python-client google-auth-oauthlib google-auth-httplib2")
        sys.exit(1)

    config = load_config()

    if not config['upload_enabled'] and not args.dry_run:
        logging.warning("YouTube upload is disabled in config. Use --dry-run to preview.")
        sys.exit(0)

    if args.file:
        # Upload specific file
        video_file = Path(args.file)
        if not video_file.exists():
            logging.error(f"File not found: {video_file}")
            sys.exit(1)

        # Extract date from filename
        date_part = video_file.name.split('_')[0]
        try:
            video_date = datetime.strptime(date_part, '%Y%m%d')
            date_str = video_date.strftime('%Y-%m-%d')
        except ValueError:
            date_str = datetime.now().strftime('%Y-%m-%d')

        schedule_data = load_schedule_data(date_str, config['device_id'])
        result = upload_video(video_file, schedule_data, config, args.dry_run)
        sys.exit(0 if result else 1)

    elif args.all:
        # Upload all un-uploaded videos
        videos = get_all_unuploaded_videos(config['device_id'])

        if not videos:
            logging.info("No un-uploaded videos found.")
            sys.exit(0)

        logging.info(f"Found {len(videos)} videos to upload")

        success_count = 0
        for video_file, date_str in videos:
            schedule_data = load_schedule_data(date_str, config['device_id'])
            result = upload_video(video_file, schedule_data, config, args.dry_run)
            if result:
                success_count += 1

        logging.info(f"Uploaded {success_count}/{len(videos)} videos")
        sys.exit(0 if success_count == len(videos) else 1)

    else:
        # Upload specific date (default: yesterday)
        if args.date:
            date_str = args.date
        else:
            yesterday = datetime.now() - timedelta(days=1)
            date_str = yesterday.strftime('%Y-%m-%d')

        video_file = get_video_for_date(date_str, config['device_id'])

        if not video_file:
            logging.error(f"No video found for date: {date_str}")
            sys.exit(1)

        if is_already_uploaded(video_file) and not args.dry_run:
            marker = video_file.parent / f"{video_file.name}.youtubed"
            url = marker.read_text().strip()
            logging.info(f"Video already uploaded: {url}")
            sys.exit(0)

        schedule_data = load_schedule_data(date_str, config['device_id'])
        result = upload_video(video_file, schedule_data, config, args.dry_run)
        sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
