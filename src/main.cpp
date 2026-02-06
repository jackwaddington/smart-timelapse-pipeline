// main.cpp

#include <iostream>
#include <exception>
#include "timelapse.hpp"

int main() {
    try {
        // 1. Instantiate the TimeLapse object (which handles initialization)
        TimeLapse timelapse;
        
        // 2. Run the main capture and video creation logic
        timelapse.run();
        
    } catch (const std::runtime_error& e) {
        // Log errors specific to setup (like failed schedule load or directory creation)
        std::cerr << "Fatal Error during setup: " << e.what() << std::endl;
        std::cerr << "Action Required: Check scheduler script output and permissions." << std::endl;
        return 1;
    } catch (const std::exception& e) {
        // Catch any other general exceptions
        std::cerr << "Unhandled Error: " << e.what() << std::endl;
        return 1;
	}
    
    return 0;
}