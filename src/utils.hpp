#pragma once

#include <string>

bool create_dir(const std::string& path);

// Changes seconds into HH:MM:SS format
std::string format_duration(double seconds);

// Reads CPU temp and returns a formatted string
std::string get_cpu_temp();