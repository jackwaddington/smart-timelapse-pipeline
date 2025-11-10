# smart-timelapse-pipeline
Automated pipeline that captures, processes, and daily publishes a dynamic, sunrise-to-sunset timelapse to YouTube.

## What problem am I trying to solve?
- Automatically generate 'content'.
- Creating in long term - changing seasons - with 'fire and forget'.
- Use [Raspberry Pi Zero W](https://www.raspberrypi.com/products/raspberry-pi-zero-w/) with it's limited resources - single core, 1ghz, 500mb ram.


## Hows does it work?
- CRON jobs start the scripts
- - timelapse.conf to hold our configurations
- - scheduler.py to check when to take pictures
  - timelapse.cpp to read the schedule, read the image capure settings, take image and make the video.
  - manager.py to upload the video, move files to NAS and free up space on the device.


## Features
- "Make Legacy" to use ... instead of ....


##Improvements
- The settings of the image take command can be edited.
- conf file?


## Libraries and tools
[configparser](https://docs.python.org/3/library/configparser.html)

[cron](https://en.wikipedia.org/wiki/Cron)

[rsync](https://en.wikipedia.org/wiki/Rsync)

[sshpass](https://sshpass.com/)


## Logs
  CPU temp during video compilation
  Time to compile video
