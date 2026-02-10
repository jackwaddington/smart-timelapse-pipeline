// timelapse.cpp

// todo
// work with new file naming format
// make output file be like timelapse_pi0cam_2025-11-14.mp4
// note that now the vid files are 200mb! but they also encoded a little faster?!
// define all the time formats
// the video that worked was 20251114-Pi0Cam-timelapse.mp4


#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <opencv2/opencv.hpp> // Video processing
#include <sstream>
#include <sys/stat.h>
#include <sys/wait.h>
#include <thread>
#include <cstring> // For strerror
#include <string>

#include "timelapse.hpp"
#include "utils.hpp"

const char* CONFIG_FILE = "conf/timelapse.conf";

// constructor
TimeLapse::TimeLapse() : photo_count(0), capture_errors(0),
    last_capture_duration_ms(0), last_capture_success(false),
    last_capture_epoch(0) {
    // 1. Ensure directories exist
    if (!create_dir(LOGS_PATH)) {
         throw std::runtime_error("Failed to create logs directory: " + std::string(LOGS_PATH));
    }

	if (!create_dir(PICS_PATH)) {
         throw std::runtime_error("Failed to create pics directory: " + std::string(PICS_PATH));
    }
    
	if (!create_dir(VIDEOS_PATH)) {
         throw std::runtime_error("Failed to create videos directory: " + std::string(VIDEOS_PATH));
    }

	// 2. Load config (camera capture setting)
	if (!load_config()) {
        throw std::runtime_error("Failed to load configuration");
    }

    // 3. Load schedule
    if (!load_today_schedule()) {
        throw std::runtime_error("Failed to load schedule");
    }
    
    // 4. Set up output directory
    auto timestamp = get_timestamp();
    std::string clean_date = date_str;
    std::replace(clean_date.begin(), clean_date.end(), '-', '_');
    
	output_dir = std::string(PICS_PATH) + filename_prefix + "_pics/";
    if (!create_dir(output_dir)) {
        throw std::runtime_error("Failed to create output directory: " + output_dir);
    }
    
    log_status("TimeLapse initialized - Output: " + output_dir);
    log_status("Today's schedule:");
    log_status("  Date: " + date_str);
    log_status("  Capture: " + start_time + " to " + end_time);
    log_status("  Interval: " + std::to_string(interval_seconds) + " seconds");
    log_status("  Expected photos: " + std::to_string(expected_photos));
}

// Private methods implementations
std::string TimeLapse::get_timestamp() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&time_t), "%Y%m%d_%H%M%S");
    return ss.str();
}

void TimeLapse::log_status(const std::string& message) {
    auto timestamp = get_timestamp();
    
    // Log to STDOUT
    std::cout << "[" << timestamp << "] " << message << std::endl;
    
    // Log to a backup file inside the logs/ directory
    std::string logfile_path = std::string(LOGS_PATH) + "timelapse.log";
    std::ofstream logfile(logfile_path, std::ios::app);
    if (logfile.is_open()) {
        logfile << "[" << timestamp << "] " << message << std::endl;
        logfile.close();
    }
}

void TimeLapse::write_status_file(const std::string& status) {
    auto now = std::chrono::system_clock::now();
    auto epoch = std::chrono::duration_cast<std::chrono::seconds>(
        now.time_since_epoch()).count();

    std::ofstream f(STATUS_FILE);
    if (!f.is_open()) {
        log_status("Warning: Could not write status file");
        return;
    }

    f << "{\n"
      << "  \"status\": \"" << status << "\",\n"
      << "  \"device_id\": \"" << device_id << "\",\n"
      << "  \"date\": \"" << date_str << "\",\n"
      << "  \"photos_captured\": " << photo_count << ",\n"
      << "  \"expected_photos\": " << expected_photos << ",\n"
      << "  \"capture_errors\": " << capture_errors << ",\n"
      << "  \"last_capture_success\": " << (last_capture_success ? "true" : "false") << ",\n"
      << "  \"last_capture_timestamp\": " << last_capture_epoch << ",\n"
      << "  \"last_capture_duration_ms\": " << std::fixed << std::setprecision(1) << last_capture_duration_ms << ",\n"
      << "  \"start_time\": \"" << start_time << "\",\n"
      << "  \"end_time\": \"" << end_time << "\",\n"
      << "  \"interval_seconds\": " << interval_seconds << ",\n"
      << "  \"updated_at\": " << epoch << "\n"
      << "}\n";
    f.close();
}

bool TimeLapse::load_config() {
    std::ifstream file(CONFIG_FILE);
    if (!file.is_open()) {
        log_status("ERROR: Could not find config file: " + std::string(CONFIG_FILE));
        return false;
    }
    
    std::string line;
    while (std::getline(file, line)) {
        size_t equals_pos = line.find('=');
        if (equals_pos != std::string::npos) {
            std::string key = line.substr(0, equals_pos);
            std::string value = line.substr(equals_pos + 1);

            // Strip leading/trailing whitespace from key and value
            key.erase(0, key.find_first_not_of(" \t\n\r"));
            key.erase(key.find_last_not_of(" \t\n\r") + 1);
            value.erase(0, value.find_first_not_of(" \t\n\r"));
            value.erase(value.find_last_not_of(" \t\n\r") + 1);
            
            if (key == "capture_command") {
                base_capture_command = value;
                log_status("Loaded config: capture_command = " + base_capture_command);
            }

			if (key == "id") {
				device_id = value;
				log_status("Loaded config: device_id = " + device_id);
			}
        }
    }
    
    // Final check to ensure the command was actually loaded
    if (base_capture_command.empty()) {
        log_status("ERROR: 'capture_command' not found in config file.");
        return false;
    }
    
    return true;
}

bool TimeLapse::load_today_schedule() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    auto tm = *std::localtime(&time_t);
    
    std::stringstream prefix_ss;
    // ss << SCHEDULES_PATH << "schedule_" << std::put_time(&tm, "%Y-%m-%d") << ".txt";
    prefix_ss << std::put_time(&tm, "%Y%m%d") << "_" << device_id;

	filename_prefix = prefix_ss.str();

	schedule_filename = filename_prefix + "_schedule.txt";
	// todo convert to json to make easier importing?
	video_filename = std::string(VIDEOS_PATH) + filename_prefix + "_timelapse.mp4";

	std::string schedule_filename_path = std::string(SCHEDULES_PATH) + schedule_filename;
   
    std::ifstream file(schedule_filename_path);
    if (!file.is_open()) {
        log_status("Error: Could not find today's schedule file: " + schedule_filename_path);
        log_status("Run the Python scheduler script first to generate the schedule");
        return false;
    }
    
    std::string line;
    while (std::getline(file, line)) {
        if (line.find("Date: ") == 0) {
            date_str = line.substr(6);
        } else if (line.find("Start: ") == 0) {
            start_time = line.substr(7);
        } else if (line.find("End: ") == 0) {
            end_time = line.substr(5);
        } else if (line.find("Interval: ") == 0) {
            try {
                size_t start = line.find(": ") + 2;
                size_t end = line.find(" seconds");
                if (end != std::string::npos) {
                    interval_seconds = std::stoi(line.substr(start, end - start));
                } else {
                    interval_seconds = std::stoi(line.substr(start));
                }
            } catch (...) {
                log_status("Error: Could not parse interval time.");
                return false;
            }
        } else if (line.find("Expected photos: ") == 0) {
            try {
                expected_photos = std::stoi(line.substr(17));
            } catch (...) {
                log_status("Error: Could not parse expected photos count.");
                return false;
            }
        }
    }
    
    if (date_str.empty() || start_time.empty() || end_time.empty() || interval_seconds <= 0) {
        log_status("Error: Essential schedule data missing or invalid.");
        return false;
    }
    
    log_status("Loaded schedule from " + schedule_filename_path);
    return true;
}

long TimeLapse::time_to_seconds(const std::string& time_str) {
    int hour = std::stoi(time_str.substr(0, 2));
    int minute = std::stoi(time_str.substr(3, 2));
    int second = std::stoi(time_str.substr(6, 2));
    return hour * 3600 + minute * 60 + second;
}

long TimeLapse::get_current_day_seconds() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    auto tm = *std::localtime(&time_t);
    return tm.tm_hour * 3600 + tm.tm_min * 60 + tm.tm_sec;
}

bool TimeLapse::is_time_to_start() {
    long current_total_sec = get_current_day_seconds();
    long start_total_sec = time_to_seconds(start_time);
    
    return current_total_sec >= start_total_sec;
}

bool TimeLapse::is_time_to_stop() {
    long current_total_sec = get_current_day_seconds();
    long end_total_sec = time_to_seconds(end_time);
    
    return current_total_sec >= end_total_sec;
}

bool TimeLapse::capture_photo() {
    photo_count++;
    
    // Cleanup date string (e.g., 2025-11-14 -> 20251114)
    std::string clean_date = date_str;
    clean_date.erase(std::remove(clean_date.begin(), clean_date.end(), '-'), clean_date.end());
    
    // Assemble filename (e.g., output_dir/20251114_0001.jpg)
    std::stringstream ss;
    ss << output_dir
		<< filename_prefix
		<< std::setfill('0')
		<< std::setw(4)
		<< photo_count
		<< ".jpg";
    std::string filename = ss.str();

	//     ss << output_dir
	// 	<< clean_date
	// 	<< "_"
	// 	<< device_id
	// 	<< "_"
	// 	<< std::setfill('0')
	// 	<< std::setw(4)
	// 	<< photo_count
	// 	<< ".jpg";
    // std::string filename = ss.str();
    
    // --- COMMAND ASSEMBLY ---
    std::string capture_command = base_capture_command;
    capture_command += " -o ";
    capture_command += filename; 
    
    if (photo_count % 10 == 1 || photo_count == 1) { 
        log_status("Capturing photo " + std::to_string(photo_count) + "/" + 
                  std::to_string(expected_photos) + " -> " + filename);
    }
    
    // 3. Execute the command
    int result = std::system(capture_command.c_str());
    
    // --- ERROR CHECKING ---

    // 1. Check if the shell failed to execute the command itself.
    if (result == -1) {
        log_status("FATAL ERROR: Failed to execute shell command (system() returned -1). Command: " + capture_command);
        capture_errors++;
        last_capture_success = false;
        return false;
    }

    // 2. Check if the command (libcamera-still) executed but returned an error code.
    // WEXITSTATUS requires <sys/wait.h>
    int exit_code = WEXITSTATUS(result);

    if (exit_code != 0) {
        // Log the failure with the specific exit code.
        std::string error_msg = "COMMAND ERROR: Capture failed. Command exit code: " + std::to_string(exit_code) + ". Command: " + capture_command;
        log_status(error_msg);
        capture_errors++;
        last_capture_success = false;
        return false;
    }

    // --- SUCCESS ---
    // If the exit_code is 0, the capture was successful.
    last_capture_success = true;
    last_capture_epoch = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    photo_files.push_back(filename);
    
    // Log success only if we didn't log the "Capturing" message earlier
    if (photo_count % 10 != 1 && photo_count != 1) {
        log_status("Photo captured successfully: " + filename);
    }
    
    return true;
}

// --- Video Creation Logic (Uses OpenCV) ---
void TimeLapse::create_video() {
    if (photo_files.empty()) {
        log_status("No photos to create video from! Skipping.");
        return;
    }

    log_status("Creating video from " + std::to_string(photo_files.size()) + " photos using OpenCV...");
    
    // 1. Read the first image to determine frame size
    cv::Mat first_image = cv::imread(photo_files[0]);
    if (first_image.empty()) {
        log_status("Error reading first image! Cannot determine frame size. Check photo integrity.");
        return;
    }

    int fps = 25; // Frame rate for the final video (25 frames per second)
    cv::Size frame_size(first_image.cols, first_image.rows);

	// --- Start Timing for Video Compilation ---
    auto start_time = std::chrono::high_resolution_clock::now();
    
	// Clean the date string
	// std::string clean_date = date_str;
    // clean_date.erase(std::remove(clean_date.begin(), clean_date.end(), '-'), clean_date.end());

    // Output file name
	// std::string video_filename = std::string(VIDEOS_PATH)
	// 								+ clean_date
	// 								+ "_"
	// 								+ device_id
	// 								+ "_timelapse_.mp4";

    // 2. Initialize the video writer
    // FOURCC 'mp4v' for MP4 container (ensure OpenCV is built with FFMPEG support)
    cv::VideoWriter video_writer(video_filename,
                                 cv::VideoWriter::fourcc('m','p','4','v'), 
                                 fps, frame_size);
    
    if (!video_writer.isOpened()) {
        log_status("Error creating cv::VideoWriter! Check dependencies (FFMPEG) and permissions.");
        return;
    }

    // 3. Loop through all captured images and write them as frames
    for (size_t i = 0; i < photo_files.size(); i++) {
		cv::Mat image = cv::imread(photo_files[i]);
        if (!image.empty()) {
			video_writer.write(image);
            if (i % 100 == 0 && i != 0) {
				std::string cpu_temp = get_cpu_temp();
				log_status("Video progress: " + std::to_string(i) + "/" + std::to_string(photo_files.size()) + "   ||   CPU: " + cpu_temp);
            }
        }
    }
    
    // 4. Release the writer to finalize the video file
    video_writer.release();

	// --- Stop Timing and Calculate Duration ---
    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed_time = end_time - start_time;
    
    double actual_video_length = (double)photo_files.size() / fps;
    log_status("Video saved as " + video_filename);
    log_status("Actual video length: " + std::to_string(actual_video_length) + " seconds");
	log_status("Video compilation finished! Time to encode: " + format_duration(elapsed_time.count()));
}

// Public methods implementation
void TimeLapse::run() {
    log_status("Waiting for start time: " + start_time);
    write_status_file("waiting");

    // Wait until start time
    while (!is_time_to_start()) {
        std::this_thread::sleep_for(std::chrono::seconds(30));
    }

    log_status("Starting automated timelapse capture!");
    write_status_file("capturing");
    
    // Capture loop
    while (!is_time_to_stop()) {
    
		// record start time
		auto capture_start = std::chrono::steady_clock::now();
    
		if (!capture_photo()) {
			log_status("Failed to capture photo, continuing...");
		}

    // record end time
	    auto capture_end = std::chrono::steady_clock::now();
	// calc diff
	    auto capture_duration = std::chrono::duration_cast<std::chrono::seconds>(capture_end - capture_start);
	    last_capture_duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(capture_end - capture_start).count();

	    // Update status file for metrics scraping
	    write_status_file("capturing");
    
    // Sleep for the remaining time to maintain the interval
		auto sleep_time = interval_seconds - capture_duration.count();
		if (sleep_time > 0) {
			std::this_thread::sleep_for(std::chrono::seconds(sleep_time));
		} else {
			log_status("Warning: Capture took longer than interval!");
		}
	}
    
    log_status("Scheduled capture complete! Captured " + std::to_string(photo_count) + " photos.");
    log_status("Expected: " + std::to_string(expected_photos) + " photos");

    // Execute video creation immediately after capture finishes
    write_status_file("creating_video");
    create_video();

    write_status_file("finished");
    log_status("Automated timelapse thread finished.");
}