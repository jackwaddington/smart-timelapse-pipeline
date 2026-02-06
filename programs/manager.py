import subprocess
import shutil
from datetime import datetime, timedelta
import configparser
from pathlib import Path
import sys
import logging 
import os 

# Define the base paths for the script locations
SCRIPT_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_PATH.parent
LOGS_DIR = PROJECT_ROOT / "logs"
SCHEDULES_DIR = PROJECT_ROOT / "schedules"
PICS_DIR = PROJECT_ROOT / "pics"
VIDEOS_DIR = PROJECT_ROOT / "videos"
CONF_DIR = PROJECT_ROOT / "conf" 

LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE_PATH = LOGS_DIR / "manager.log"

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s', 
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)

class TimeLapseManager:
    def __init__(self, config_file=CONF_DIR / "timelapse.conf"):
        # Ensure working directories exist
        PICS_DIR.mkdir(exist_ok=True)
        VIDEOS_DIR.mkdir(exist_ok=True)
        CONF_DIR.mkdir(exist_ok=True) 
        
        self.config_file = config_file
        self.load_config() 
    
    def load_config(self):
        """Load configuration from file. Creates default if none exists."""
        config = configparser.ConfigParser()
        
        # Default configuration
        defaults = {
            'BACKUP': {
                'nas_host': 'your-nas-ip',
                'nas_module': 'timelapse',
                'backup_enabled': 'true',
                'delete_after_backup': 'false'
            },
            'CLEANUP': {
                'keep_days': '5',
                'keep_videos': '5',
                'cleanup_enabled': 'true'
            },
            'YOUTUBE': {
                'upload_enabled': 'false', 
                'client_secrets_file': 'client_secrets.json',
                'credentials_file': 'youtube_credentials.json',
                'default_title': 'Daily Timelapse {device_id} {date}',
                'default_description': 'Automated daily timelapse from {device_id} on {date}. Sunrise: {sunrise}, Sunset: {sunset}. Captured with Raspberry Pi', 
                'default_tags': 'timelapse,raspberry pi,automated,daily',
                'default_privacy': 'public'
            },
            'PATHS': {
                'timelapse_dir': '.', 
            },
            'DEVICE': {
                'id': 'Pi0Cam' 
            }
        }
        
        # Write default config if it doesn't exist
        if not self.config_file.exists():
            for section, options in defaults.items():
                if not config.has_section(section):
                    config.add_section(section)
                for key, value in options.items():
                    config.set(section, key, value)
            
            with open(self.config_file, 'w') as f:
                config.write(f)
            
            logging.warning(f"Created default config file: {self.config_file}")
            print(">>> Please edit the configuration file with your NAS and YouTube settings. <<<")
        
        # Load the config
        config.read(self.config_file)
        self.config = config
        
        # Save device ID for use in logs and paths
        self.device_id = self.config.get('DEVICE', 'id', fallback='UnknownDevice')
        logging.info(f"Configuration loaded. Device ID set to: {self.device_id}")

    
    def rsync_to_nas(self, source_dir, remote_folder_name):
        """
        Backup photo directory to NAS using rsync daemon.
        Much simpler than SSH approach - no authentication needed.
        """
        if not self.config.getboolean('BACKUP', 'backup_enabled', fallback=False):
            logging.warning("Backup disabled in configuration. Skipping rsync.")
            return False

        nas_host = self.config.get('BACKUP', 'nas_host', fallback='localhost')
        nas_module = self.config.get('BACKUP', 'nas_module', fallback='timelapse')

        # Build the rsync daemon URL
        # Format: rsync://host/module/device_id/remote_folder_name/
        destination = f"rsync://{nas_host}/{nas_module}/{self.device_id}/{remote_folder_name}/"
        
        # Simple rsync command - no authentication needed
        rsync_cmd = ['rsync', '-avh', f"{str(source_dir)}/", destination]
        
        logging.info(f"Starting photo backup: {source_dir.name} -> {destination}")
        
        try:
            result = subprocess.run(rsync_cmd, check=True, capture_output=True, text=True)
            logging.info("Photo backup completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Backup failed (Code {e.returncode}). Stderr: {e.stderr.strip()}")
            return False
        except Exception as e:
            logging.error(f"Backup error: {str(e)}", exc_info=True)
            return False

        
    def cleanup_old_files(self):
        """Clean up old backed-up photos and videos based on retention policy.

        Only deletes items that have been confirmed backed up (.backed_up marker).
        disk_cleanup.py handles emergency deletion of unbacked items if disk fills.
        """
        if not self.config.getboolean('CLEANUP', 'cleanup_enabled', fallback=False):
            logging.warning("Cleanup disabled in configuration. Skipping cleanup.")
            return

        keep_days = self.config.getint('CLEANUP', 'keep_days', fallback=5)
        keep_videos = self.config.getint('CLEANUP', 'keep_videos', fallback=5)

        logging.info(f"Starting cleanup: backed-up photos older than {keep_days} days, backed-up videos older than {keep_videos} days.")

        cutoff_date = datetime.now() - timedelta(days=keep_days)
        video_cutoff_date = datetime.now() - timedelta(days=keep_videos)

        removed_dirs = 0
        skipped_unbacked = 0
        removed_videos = 0
        skipped_unbacked_videos = 0

        # --- LOOP 1: Clean up old PHOTO directories in PICS_DIR ---
        for item_path in PICS_DIR.iterdir():
            item_name = item_path.name

            if item_path.is_dir() and item_name.endswith('_pics'):
                try:
                    date_part = item_name.split('_')[0]
                    dir_date = datetime.strptime(date_part, '%Y%m%d')

                    if dir_date < cutoff_date:
                        # Only delete if backed up
                        if (item_path / ".backed_up").exists():
                            logging.info(f"Removing old photo directory: {item_path}")
                            shutil.rmtree(item_path)
                            removed_dirs += 1
                        else:
                            logging.warning(f"Skipping {item_name} - not backed up yet")
                            skipped_unbacked += 1
                except (IndexError, ValueError):
                    logging.warning(f"Skipping directory with unexpected name format: {item_name}")
                except OSError as e:
                    logging.error(f"Failed to remove directory {item_path}: {e}")

        # --- LOOP 2: Clean up old VIDEO files in VIDEOS_DIR ---
        youtube_enabled = self.config.getboolean('YOUTUBE', 'upload_enabled', fallback=False)

        for item_path in VIDEOS_DIR.iterdir():
            item_name = item_path.name

            if item_path.is_file() and item_name.endswith('_timelapse.mp4'):
                try:
                    date_part = item_name.split('_')[0]
                    video_date = datetime.strptime(date_part, '%Y%m%d')

                    if video_date < video_cutoff_date:
                        # Require .backed_up AND .youtubed (if YouTube enabled) before deletion
                        backup_marker = VIDEOS_DIR / f"{item_name}.backed_up"
                        youtube_marker = VIDEOS_DIR / f"{item_name}.youtubed"

                        is_backed_up = backup_marker.exists()
                        is_on_youtube = youtube_marker.exists() or not youtube_enabled

                        if is_backed_up and is_on_youtube:
                            logging.info(f"Removing old video: {item_path}")
                            item_path.unlink()
                            if backup_marker.exists():
                                backup_marker.unlink()
                            if youtube_marker.exists():
                                youtube_marker.unlink()
                            removed_videos += 1
                        else:
                            reasons = []
                            if not is_backed_up:
                                reasons.append("not backed up")
                            if not is_on_youtube:
                                reasons.append("not on YouTube")
                            logging.warning(f"Skipping {item_name} - {', '.join(reasons)}")
                            skipped_unbacked_videos += 1
                except ValueError:
                    logging.warning(f"Skipping video with unexpected name format: {item_name}")
                except OSError as e:
                    logging.error(f"Failed to remove video file {item_path}: {e}")

        logging.info(f"Cleanup complete: removed {removed_dirs} photo dirs, {removed_videos} videos. Skipped {skipped_unbacked} unbacked photos, {skipped_unbacked_videos} unbacked videos.")


    def _load_schedule_metadata(self, date_str):
        """Loads sunrise and sunset from the TXT schedule file."""
        schedule_path = SCHEDULES_DIR / f"{date_str}_{self.device_id}_schedule.txt" 
        schedule_data = {'sunrise': 'N/A', 'sunset': 'N/A', 'date': date_str, 'device_id': self.device_id}
        
        if not schedule_path.exists():
            logging.warning(f"Schedule file not found: {schedule_path}")
            return schedule_data
        
        try:
            with open(schedule_path, 'r') as f:
                for line in f:
                    if line.startswith("Sunrise:"):
                        schedule_data['sunrise'] = line.split(': ', 1)[1].strip()
                    elif line.startswith("Sunset:"):
                        schedule_data['sunset'] = line.split(': ', 1)[1].strip()
            
            return schedule_data
        except Exception as e:
            logging.error(f"Error reading schedule file {schedule_path}: {e}", exc_info=True)
            return schedule_data

    
    def upload_to_youtube(self, video_file, schedule_data):
        """Upload video to YouTube using youtube_upload module."""
        if not self.config.getboolean('YOUTUBE', 'upload_enabled', fallback=False):
            logging.info("YouTube upload disabled in config.")
            return None

        # Check if already uploaded
        youtube_marker = VIDEOS_DIR / f"{video_file.name}.youtubed"
        if youtube_marker.exists():
            url = youtube_marker.read_text().strip()
            logging.info(f"Video already uploaded to YouTube: {url}")
            return url

        try:
            # Import and use the youtube_upload module
            from youtube_upload import load_credentials, load_config as load_yt_config, upload_video

            yt_config = load_yt_config()
            result = upload_video(video_file, schedule_data, yt_config, dry_run=False)
            if result:
                logging.info(f"YouTube upload successful: {result}")
            return result
        except ImportError as e:
            logging.error(f"YouTube upload module not available: {e}")
            logging.error("Install with: pip3 install google-api-python-client google-auth-oauthlib")
            return None
        except Exception as e:
            logging.error(f"YouTube upload failed: {e}", exc_info=True)
            return None
    
    def process_completed_timelapse(self, date_str):
        """Process a completed timelapse: backup, upload, cleanup"""
        logging.info(f"Starting process for timelapse date {date_str} (Device: {self.device_id})")
        
        clean_date = date_str.replace('-', '')
        
        schedule_data = self._load_schedule_metadata(clean_date)
        
        photo_dir = None
        for item_path in PICS_DIR.iterdir():
            if item_path.is_dir() and item_path.name.startswith(f'{clean_date}_{self.device_id}_pics'):
                photo_dir = item_path
                break
        
        if not photo_dir:
            logging.warning(f"No photo directory found for {date_str}. Aborting processing.")
            return

        video_file = VIDEOS_DIR / f'{clean_date}_{self.device_id}_timelapse.mp4'
        
        # Photo Folder: YYYYMMDD-[Device_ID]-timelaps_pics
        nas_photo_folder_name = f"{clean_date}_{self.device_id}_pics"
        
        # Video File: YYYYMMDD-[Device_ID]-timelapse.mp4
        nas_video_file_name = f"{clean_date}_{self.device_id}_timelapse.mp4"
        
        # Step 1: Backup to NAS (Photos)
        is_backup_success = self.rsync_to_nas(photo_dir, nas_photo_folder_name)
        
        if is_backup_success:
            # Create backup marker for disk_cleanup.py to know this folder is safe to delete
            marker_path = photo_dir / ".backed_up"
            try:
                marker_path.touch()
                logging.info(f"Created backup marker: {marker_path}")
            except OSError as e:
                logging.error(f"Failed to create backup marker: {e}")

            # Step 1b: Optional immediate deletion of photos
            if self.config.getboolean('BACKUP', 'delete_after_backup', fallback=False):
                try:
                    shutil.rmtree(photo_dir)
                    logging.info(f"Photo directory deleted after successful backup: {photo_dir}")
                except OSError as e:
                    logging.error(f"Failed to delete photo directory after backup: {e}")
            
    # Step 1c: Backup the Video File
            if video_file.exists() and self.config.getboolean('BACKUP', 'backup_enabled', fallback=False):
                nas_host = self.config.get('BACKUP', 'nas_host', fallback='localhost')
                nas_module = self.config.get('BACKUP', 'nas_module', fallback='timelapse')

                # Build rsync daemon URL for the video file
                video_destination = f"rsync://{nas_host}/{nas_module}/{self.device_id}/{nas_video_file_name}"
                
                # Simple rsync command - no authentication needed
                video_backup_cmd = ['rsync', '-avh', str(video_file), video_destination]
                
                logging.info(f"Starting video backup: {video_file.name} -> {video_destination}")
                
                try:
                    subprocess.run(video_backup_cmd, check=True, capture_output=True, text=True)
                    logging.info("Video backed up successfully")
                    # Create backup marker for disk_cleanup.py
                    video_marker_path = VIDEOS_DIR / f"{video_file.name}.backed_up"
                    try:
                        video_marker_path.touch()
                        logging.info(f"Created video backup marker: {video_marker_path}")
                    except OSError as e:
                        logging.error(f"Failed to create video backup marker: {e}")
                except subprocess.CalledProcessError as e:
                    logging.error(f"Video backup failed (Code {e.returncode}). Stderr: {e.stderr.strip()}")
                except Exception as e:
                    logging.error(f"Video backup error: {str(e)}", exc_info=True)
            else:
                logging.warning("Video file not found or backup is disabled, skipping video backup.")

        # Step 2: Upload to YouTube
        if video_file.exists():
            self.upload_to_youtube(video_file, schedule_data)

        # Step 3: Cleanup old files
        self.cleanup_old_files()
        
        logging.info(f"Processing complete for {date_str}")

def main():
    # delete schedule text files
    # clean up logs?
    
    try:
        manager = TimeLapseManager()
        
        if len(sys.argv) > 1:
            date_str = sys.argv[1]
        else:
            yesterday = datetime.now() - timedelta(days=1)
            date_str = yesterday.strftime('%Y-%m-%d')

        # load config file?    
        manager.process_completed_timelapse(date_str)
        
    except configparser.Error as e:
        logging.critical(f"A configuration file error occurred: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logging.critical(f"A fatal and unexpected error occurred in main execution: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Ensure we run from the project root directory
    if Path.cwd().name != PROJECT_ROOT.name:
        os.chdir(PROJECT_ROOT)

    main()