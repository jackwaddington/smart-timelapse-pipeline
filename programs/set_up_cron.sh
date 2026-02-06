#!/bin/bash

# --- Configuration ---
# IMPORTANT: Define the absolute path to your project directory.
PROJECT_DIR="/home/jack/github/auto-timelapse/v5-zero_test"

# Define the block of cron jobs to be added.
# NOTE: The last line MUST be a newline character (\n) for crontab to read the file correctly.
CRON_JOBS="
# START: AUTO-TIMELAPSE JOBS
# Generate tomorrow's schedule (end of day)
59 23 * * * cd ${PROJECT_DIR} && python3 ./programs/scheduler.py

# Start daily timelapse at 3:00 AM
0 3 * * * cd ${PROJECT_DIR} && nohup ./programs/timelapse > logs/todays_run.log 2>&1 &

# Process completed timelapse (after midnight, so "yesterday" = day that just ended)
0 1 * * * cd ${PROJECT_DIR} && python3 ./programs/manager.py

# Log free disk space
5 1 * * * cd ${PROJECT_DIR} && python3 ./programs/disk_checker.py

# Disk-based cleanup (after manager sets .backed_up markers)
10 1 * * * cd ${PROJECT_DIR} && python3 ./programs/disk_cleanup.py
# END: AUTO-TIMELAPSE JOBS
"
# ---------------------

echo "--- Starting Cron Job Setup (Bash) ---"
echo "Target directory: ${PROJECT_DIR}"

# 1. Retrieve the current crontab or initialize an empty string if none exists
CURRENT_CRONTAB=$(crontab -l 2>/dev/null)

# 2. Check if the jobs are already installed
if echo "${CURRENT_CRONTAB}" | grep -q "# START: AUTO-TIMELAPSE JOBS"; then
    echo "Cron jobs block already found. Installation skipped."
else
    echo "Jobs not found. Installing now..."
    
    # 3. Combine the existing crontab with the new jobs
    # The 'printf' command handles the variables and correct formatting.
    NEW_CRONTAB="${CURRENT_CRONTAB}"
    NEW_CRONTAB+="${CRON_JOBS}"

    # 4. Pipe the combined content back into crontab
    # The '<<EOF' here is a heredoc, piping multi-line input to the crontab command.
    echo "${NEW_CRONTAB}" | crontab -
    
    if [ $? -eq 0 ]; then
        echo -e "\n✅ Success! New cron jobs have been installed."
        echo "New crontab contents (simplified view):"
        echo "${CRON_JOBS}" | grep "0 " | sed 's/^/   -> /' # Just prints the actual job lines
    else
        echo -e "\n❌ Failed to install cron jobs. Check permissions."
    fi
fi

echo -e "\nTo view your installed cron jobs, run the following command:"
echo "crontab -l"