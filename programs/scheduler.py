import requests
from datetime import datetime, timedelta
import os
import configparser
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import sys
import logging

# --- Logging Setup ---
SCRIPT_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_PATH.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE_PATH = LOGS_DIR / "scheduler.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler(sys.stdout) # Also output INFO to console
    ]
)

SCHEDULE_DIR = "./schedules" 
CONFIG_FILE = "./conf/timelapse.conf"

class DailyTimeLapseScheduler:
    
    def __init__(self, config_file=CONFIG_FILE): 
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self):
        """Load configuration from the conf file using configparser."""
        
        # Read the config file
        read_files = self.config.read(self.config_file)
        
        if not read_files:
            error_msg = f"Could not find or read configuration file: {self.config_file}"
            logging.critical(error_msg)
            sys.exit(1)
            
        # Check for the SCHEDULER section
        if 'SCHEDULER' not in self.config:
            error_msg = f"Configuration file '{self.config_file}' is missing the '[SCHEDULER]' section."
            logging.critical(error_msg)
            sys.exit(1)

        # Retrieve and convert SCHEDULER settings from the conf file
        try:
            self.latitude = self.config.getfloat('SCHEDULER', 'latitude')
            self.longitude = self.config.getfloat('SCHEDULER', 'longitude')
            self.target_video_length_seconds = self.config.getint('SCHEDULER', 'target_video_length_seconds')
            self.target_fps = self.config.getint('SCHEDULER', 'target_fps')
            self.min_interval_seconds = self.config.getint('SCHEDULER', 'min_interval_seconds')
            self.max_interval_seconds = self.config.getint('SCHEDULER', 'max_interval_seconds')
            self.buffer_minutes = self.config.getint('SCHEDULER', 'buffer_minutes')
            self.timezone_str = self.config.get('SCHEDULER', 'timezone') 
            self.device_id = self.config.get('DEVICE', 'id', fallback='UndefinedDeviceID')

        except configparser.NoOptionError as e:
            logging.critical(f"Missing required option in configuration file: {e}")
            sys.exit(1)
        except ValueError as e:
            logging.critical(f"Invalid value type for a configuration option: {e}")
            sys.exit(1)
        
        # Timezone Validation
        try:
            ZoneInfo(self.timezone_str)
            logging.info(f"Configuration loaded successfully. Device ID: {self.device_id}")
        except ZoneInfoNotFoundError:
            error_msg = f"Invalid timezone name in config: '{self.timezone_str}'. Must be a valid IANA Time Zone (e.g., 'Europe/Helsinki')."
            logging.critical(error_msg)
            sys.exit(1)

    def get_sun_times(self, date=None):
        """Get sunrise and sunset times using sunrise-sunset.org API"""
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime('%Y-%m-%d')
        
        url = f"https://api.sunrise-sunset.org/json"
        params = {
            'lat': self.latitude,
            'lng': self.longitude,
            'date': date_str,
            'formatted': 0
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'OK':
                local_timezone = ZoneInfo(self.timezone_str)
                
                sunrise_utc = datetime.fromisoformat(data['results']['sunrise'].replace('Z', '+00:00'))
                sunset_utc = datetime.fromisoformat(data['results']['sunset'].replace('Z', '+00:00'))
               
                # Convert to local time
                sunrise_local = sunrise_utc.astimezone(local_timezone).replace(tzinfo=None)
                sunset_local = sunset_utc.astimezone(local_timezone).replace(tzinfo=None)
                logging.info(f"Configuration loaded successfully. Device ID: {self.device_id}, Sunrise: {sunrise_local.strftime('%H:%M:%S')}, Sunset: {sunset_local.strftime('%H:%M:%S')}")
                return sunrise_local, sunset_local
            else:
                logging.error(f"Sunrise-sunset API returned status: {data['status']} for date {date_str}")
                raise Exception(f"API error: {data['status']}")
                
        except Exception as e:
            logging.error(f"Error getting sun times from API: {e}. Falling back to default times.")
            # Fallback to a fixed 6 AM to 6 PM if API call fails
            base_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            return base_date.replace(hour=6), base_date.replace(hour=18)
    
    def calculate_schedule(self, date=None):
        """Calculate the optimal schedule for a given date"""
        if date is None:
            date = datetime.now()
        
		# retrieve sunrise & sunset times
        sunrise, sunset = self.get_sun_times(date)
        
		# add on the buffer
        start_time = sunrise - timedelta(minutes=self.buffer_minutes)
        end_time = sunset + timedelta(minutes=self.buffer_minutes)
        
		# calc seconds interval to achieve 30 second video
        total_duration_seconds = (end_time - start_time).total_seconds()
        target_frames = self.target_video_length_seconds * self.target_fps
        optimal_interval = total_duration_seconds / target_frames
        
		# clamp values
        interval_seconds = max(
            self.min_interval_seconds,
            min(self.max_interval_seconds, optimal_interval)
        )
        
        actual_photos = int(total_duration_seconds / interval_seconds)
        actual_video_length = actual_photos / self.target_fps
        
        schedule = {
            'date': date.strftime('%Y-%m-%d'),
            'sunrise': sunrise.strftime('%H:%M:%S'),
            'sunset': sunset.strftime('%H:%M:%S'),
            'start_time': start_time.strftime('%H:%M:%S'),
            'end_time': end_time.strftime('%H:%M:%S'),
            'total_duration_hours': round(total_duration_seconds / 3600, 2),
            'interval_seconds': int(interval_seconds),
            'expected_photos': actual_photos,
            'expected_video_length_seconds': round(actual_video_length, 1),
            'filename_prefix' : f"{date.strftime('%Y%m%d')}_{self.device_id}_",
            'schedule_filename' : f"{date.strftime('%Y%m%d')}_{self.device_id}_schedule.txt",
            # should we define here video name?
            'video_filename' : f"videos/{date.strftime('%Y%m%d')}_{self.device_id}_timelapse.mp4",
            'filename' : f"schedule_{date.strftime('%Y-%m-%d')}.txt",
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return schedule


    def save_daily_schedule(self, schedule):
        """Save schedule to daily file"""
        
        # Ensure the schedules directory exists 
        os.makedirs(SCHEDULE_DIR, exist_ok=True) 

        # Define the full path 
        
        filepath = os.path.join(SCHEDULE_DIR, schedule['schedule_filename']) 
        # filepath = os.path.join(SCHEDULE_DIR, schedule['filename']) 

        # Write the TXT file
        with open(filepath, 'w') as f:
            f.write(f"DAILY TIMELAPSE SCHEDULE ({self.device_id})\n")
            f.write("=" * 25 + "\n\n")
            f.write(f"Date: {schedule['date']}\n")
            f.write(f"Sunrise: {schedule['sunrise']}\n")
            f.write(f"Sunset: {schedule['sunset']}\n\n")
            f.write(f"Capture window:\n")
            f.write(f"Start: {schedule['start_time']}\n")
            f.write(f"End: {schedule['end_time']}\n")
            f.write(f"Duration: {schedule['total_duration_hours']} hours\n\n")
            f.write(f"Photo settings:\n")
            f.write(f"Interval: {schedule['interval_seconds']} seconds\n")
            f.write(f"Expected photos: {schedule['expected_photos']}\n")
            f.write(f"Expected video length: {schedule['expected_video_length_seconds']} seconds\n\n")
            f.write(f"Filename prefix: {schedule['filename_prefix']}\n")
            f.write(f"Schedule filename: {schedule['schedule_filename']}\n")
            f.write(f"Video filename: {schedule['video_filename']}\n\n")
            f.write(f"Generated: {schedule['generated_at']}\n")
        
        logging.info(f"Schedule saved to {filepath}")
        return schedule
    
def	 print_feedback(scheduler, today_schedule):
        """Put some stuff to stdout for testing"""
        print("\nToday's Timelapse Schedule:")
        print(f"Device ID: {scheduler.device_id}")
        print(f"Sunrise-to-sunset with buffers: {today_schedule['start_time']} to {today_schedule['end_time']}")
        print(f"Photo every {today_schedule['interval_seconds']} seconds")
        print(f"Expected: {today_schedule['expected_photos']} photos")
        print(f"Video length: {today_schedule['expected_video_length_seconds']} seconds")
            

def main():
    try:
        # instanciate the scheduler
        scheduler = DailyTimeLapseScheduler()
        
		# make todays scheduler
        today_schedule = scheduler.calculate_schedule()
        
		# save todays schedule
        scheduler.save_daily_schedule(today_schedule)
        
        # feedback to console for testing
        print_feedback(scheduler, today_schedule)
                  
    except Exception as e:
        # Catch any unexpected runtime errors not handled above
        logging.critical(f"An unexpected fatal error occurred in main execution: {e}", exc_info=True)

if __name__ == "__main__":
    if Path.cwd().name != PROJECT_ROOT.name:
        os.chdir(PROJECT_ROOT)
    main()
