// timelapse.hpp

#pragma once

#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <fstream>

// --- Constants ---
#define LOGS_PATH "logs/"
#define SCHEDULES_PATH "schedules/"
#define PICS_PATH "pics/"
#define VIDEOS_PATH "videos/"

// --- Constants ---
#define STATUS_FILE "/tmp/timelapse_status.json"

// --- Class Definition ---
class TimeLapse {
private:
    std::string output_dir;
    int photo_count;
    std::vector<std::string> photo_files;
	std::string base_capture_command;
	std::string device_id;
	std::string filename_prefix;
	std::string schedule_filename;
	std::string video_filename;

    // Schedule data
    std::string date_str;
    std::string start_time;
    std::string end_time;
    int interval_seconds;
    int expected_photos;

    // Metrics tracking
    int capture_errors;
    double last_capture_duration_ms;
    bool last_capture_success;
    long last_capture_epoch;

    // Private utility methods
    std::string get_timestamp();
    void log_status(const std::string& message);
    bool load_today_schedule();
	bool load_config();
    void write_status_file(const std::string& status);

    // Time conversion methods
    long time_to_seconds(const std::string& time_str);
    long get_current_day_seconds();
    bool is_time_to_start();
    bool is_time_to_stop();

    // Core capture/video methods
    bool capture_photo();
    void create_video();

public:
    // Constructor
    TimeLapse();

    // Main run method
    void run();
};

extern const char* CONFIG_FILE;