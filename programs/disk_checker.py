import subprocess
import sys
import logging
from datetime import datetime
from pathlib import Path
import os

# --- Project Path Setup (CRITICAL for Cron Jobs) ---
# Define the base path for the script location (i.e., programs/)
SCRIPT_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_PATH.parent
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure the logs directory exists
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE_PATH = LOGS_DIR / "disk_check.log"
# ----------------------------------------------------

def setup_logger():
    """
    Configures a logger to append output ONLY to the disk_check.log file.
    This prevents unnecessary console spam when run by cron.
    """
    logger = logging.getLogger('disk_check')
    # Set level to INFO to capture the message we send
    logger.setLevel(logging.INFO)
    
    # Use FileHandler to append the output (no streaming to stdout needed here)
    file_handler = logging.FileHandler(LOG_FILE_PATH)
    # Define a simple format for the log line: [Timestamp] Raw df output
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    
    # Prevent the output from being duplicated by the root logger
    logger.propagate = False
    
    if not logger.handlers:
        logger.addHandler(file_handler)
    
    return logger

def check_disk_space():
    """
    Runs 'df -h', filters for the root partition, and logs the result.
    """
    logger = setup_logger()
    
    # Get the current timestamp (redundant with logging, but helpful for internal check)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # Run the command
        result = subprocess.run(
            ['df', '-h'], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        # Filter the output for the root device.
        # This typically looks like '/dev/root' or similar.
        for line in result.stdout.splitlines():
            if '/dev/root' in line:
                # Log the filtered line. The logger handles the timestamp prefix.
                logger.info(line.strip())
                return
        
        logger.warning("Could not find '/dev/root' partition in df output.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Command 'df -h' failed: {e.stderr.strip()}")
    except Exception as e:
        logger.critical(f"An unexpected error occurred during disk check: {e}")

if __name__ == '__main__':
    # Ensure the script runs from the project root for consistent pathing
    if Path.cwd().name != PROJECT_ROOT.name:
        os.chdir(PROJECT_ROOT)
        
    check_disk_space()