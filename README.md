# smart-timelapse-pipeline
Automated pipeline that captures, processes, and daily publishes a dynamic, sunrise-to-sunset timelapse to YouTube.

At the non-technical level - 'lets share each day'.

[Youtube](https://www.youtube.com/@RoihuCam)


## What problem am I trying to solve?
- Automatically generate 'content'.
- Photography might be the recording of light. We can use automation to take pictures where there is light - from sunrise to sunset.
- Creating long term observation with 'fire and forget'.
- Use [Raspberry Pi Zero W](https://www.raspberrypi.com/products/raspberry-pi-zero-w/) with it's limited resources - single core, 1ghz, 500mb ram.


## Hows does it work?
- timelapse.conf to hold our configurations
- Makefile to compile the CPP and set up the CRON jobs
- CRON jobs start the scripts
  - scheduler.py to check when to take pictures
  - timelapse.cpp to read the schedule, read the image capure settings, take image and make the video.
  - manager.py to upload the video, move files to NAS and free up space on the device.


## Features
- "Make Legacy" to use older Raspbery Pi camera libraries for the Pi Zero __remove__
- We can use .conf file to say which instruction to use for the R-Pi camera on newer Pis.


## Improvements
- The settings of the 'take image' take command can be edited.
- conf file?


## Libraries and tools
[configparser](https://docs.python.org/3/library/configparser.html)
This is a really handy library to parse config files - letting me set variables externally of programs.

[logging](https://docs.python.org/3/library/logging.html)
Another handy library that makes nice logfiles.

[cron](https://en.wikipedia.org/wiki/Cron)
Scheduluer built into the system.

[rsync](https://en.wikipedia.org/wiki/Rsync)
CP to copy a file, SCP to copy over network, Rsync expands on those capabilities.

[sshpass](https://sshpass.com/)
I had issues with key-based access to my NAS and this provides a workaround by locally storing a password.

[rpicam-still](https://www.raspberrypi.com/documentation/computers/camera_software.html#rpicam-apps)
Raspberry Pi camera library. 

## Logs
- CPU temp during video compilation
- Time to compile video

## Backups
To stop the memory card clogging up, we send files to a NAS for backup.

- Clear files to NAS daily, into a directory with [Device_ID] (defined in .conf).
- Folder with YYYYMMDD-[Device_ID]-timelaps_pics for the pics
- File with YYYYMMDD-[Device_ID]-timelapse.mp4 for the video
- Upload to Youtube.
- Delete after 4 days (defined in .conf)

## Health check

- How do we know everything is okay?
- Could we send 'critical' logs?

## Backlog

I have many projects I want to build. Some features I would like to explore:

- use execvp() instead of std::system.
- text overlay with opencv.
- remove files, regardless of backup, when disk space is at X
- - perhaps remove images first, until diskspace < 60%, and then remove oldest video.
