// utils.cpp

#include "utils.hpp"
#include <cerrno>
#include <cstring>
#include <cmath>
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <sys/stat.h>

// Creates a directory. Returns true if successful or if it already exists.
bool create_dir(const std::string& path) {
    // 0777 grants read/write/execute permission for everyone
    if (mkdir(path.c_str(), 0777) == -1) {
        if (errno == EEXIST) {
            return true; 
        } else {
            std::cerr << "Error creating directory " << path << ": " << strerror(errno) << std::endl;
            return false;
        }
    }
    return true;
}

// Formats seconds (double) into HH:MM:SS string format.
std::string format_duration(double seconds) {
    // Round to the nearest second
    long total_seconds = static_cast<long>(std::round(seconds));
    long h = total_seconds / 3600;
    long m = (total_seconds % 3600) / 60;
    long s = total_seconds % 60;
    
    std::stringstream ss;
    ss << std::setfill('0') << std::setw(2) << h << ":"
       << std::setfill('0') << std::setw(2) << m << ":"
       << std::setfill('0') << std::setw(2) << s;
    return ss.str();
}

// Reads the system CPU temperature file and returns a formatted string (e.g., "68.5°C").
std::string get_cpu_temp() {
    std::ifstream temp_file("/sys/class/thermal/thermal_zone0/temp");
    if (!temp_file.is_open()) {
        return "Temp N/A";
    }

    int temp_milli = 0;
    if (temp_file >> temp_milli) {
        // Convert millidegrees (e.g., 54200) to degrees Celsius (e.g., 54.2)
        double temp_c = static_cast<double>(temp_milli) / 1000.0;
        
        // Use a stringstream to format the output to one decimal place, like "54.2°C"
        std::stringstream ss;
        ss << std::fixed << std::setprecision(1) << temp_c << "°C";
        return ss.str();
    }

    return "Temp Read Error";
}