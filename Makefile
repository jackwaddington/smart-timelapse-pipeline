# ==============================================================================
# Makefile for C++ Project - Multi-File Structure
# ------------------------------------------------------------------------------
# Camera command is configured in conf/timelapse.conf (capture_command setting)
# ==============================================================================

# --- Configuration Variables ---

SHELL := /bin/bash

# Compiler and Flags
CC := g++
CFLAGS := -Wall -Wextra -std=c++17 -g -c
INC_FLAGS := -Isrc
LDFLAGS := -Wall -Wextra -std=c++17 -g

# Directory Setup
PROG_DIR := programs
OBJ_DIR := build/obj
DATA_DIRS := logs schedules
BUILD_ROOT := build

# OpenCV flags using pkg-config
OPENCV_C_FLAGS := $(shell pkg-config --cflags opencv4)
OPENCV_L_FLAGS := $(shell pkg-config --libs opencv4)

# File Names
SOURCE_FILES := main.cpp timelapse.cpp utils.cpp
TARGET_EXEC := timelapse
CRON_SETUP_SCRIPT := programs/set_up_cron.sh

# Full paths
EXECUTABLE := $(PROG_DIR)/$(TARGET_EXEC)
OBJECTS := $(addprefix $(OBJ_DIR)/, $(SOURCE_FILES:.cpp=.o))

# ------------------------------------------------------------------------------

# --- Targets ---

.PHONY: all build run setup-cron clean setup

# Default target: builds the program AND installs cron jobs
all: setup build setup-cron

# Target to prepare the environment (create data folders, set script permissions)
setup: $(DATA_DIRS) $(PROG_DIR)
	@echo "Ensuring scripts are executable..."
	@chmod +x $(CRON_SETUP_SCRIPT) || true

# Target to compile and link the C++ program
build: setup $(EXECUTABLE)

# --- Rule for linking the final executable ---
$(EXECUTABLE): $(OBJECTS)
	@echo "Linking objects to create $(TARGET_EXEC)..."
	$(CC) $(LDFLAGS) $^ -o $@ $(OPENCV_L_FLAGS)
	@echo "Compilation complete. Executable saved to $(EXECUTABLE)"

# This pattern rule says: To make any file named build/obj/%.o, use 
# the source file src/%.cpp. The % acts as a wildcard for 'main', 'timelapse', 'utils', etc.
$(OBJ_DIR)/%.o: src/%.cpp
	@echo "Compiling $<..."
	@mkdir -p $(OBJ_DIR)
	$(CC) $(CFLAGS) $(INC_FLAGS) $< -o$@ $(OPENCV_C_FLAGS)

# --- Rules to create Directories ---
$(PROG_DIR) $(DATA_DIRS):
	@mkdir -p $@

# Target to install the cron job after successful build
setup-cron: build
# 	@echo "cron setup disabled for testing"
	@echo "Ensuring project cron jobs are set up..."
	@if [ -f "$(CRON_SETUP_SCRIPT)" ]; then \
		echo "Executing cron setup script: $(CRON_SETUP_SCRIPT)"; \
		./$(CRON_SETUP_SCRIPT); \
	else \
		echo "FATAL: Cron setup script ($(CRON_SETUP_SCRIPT)) not found. Check path."; \
		exit 1; \
	fi

# Target to run the compiled program
run: build
	@echo "Running $(TARGET_EXEC):"
	@./$(EXECUTABLE)

# Target to clean up the compiled executable, generated files/data, and objects
clean:
	@echo "Cleaning up..."
	@rm -f $(EXECUTABLE)
	@echo "Remove the entire build directory (including obj)"
	@rm -rf $(BUILD_ROOT)
# 	@echo "Remove logs and schedules"
# 	@rm -rf $(DATA_DIRS)
	@rmdir --ignore-fail-on-non-empty $(PROG_DIR) || true
	@echo "Removing cron jobs"
	@crontab -l | sed '/# START: AUTO-TIMELAPSE JOBS/,/# END: AUTO-TIMELAPSE JOBS/d' | crontab - || true
	@echo "Cleanup finished."