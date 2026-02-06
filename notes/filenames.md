# programs

## disk_checker.py
run from CRON. logs disk space.

## manager.py
backs up, sends to YouTube. cleans up.

## scheduler.py
Defines the following days schedule.

## set_up_cron.sh
Puts the CRON jobs in place.


# logs

## automated_timelapse_run.log
produced by the cpp?

## daily_run.log
out put of program as it is run in bgnd - so this is like a log, but set up a bit more flamboyantly

## disk_check.log
log of available disk space. really needs taken up a level. syslog server?

## manager.log


## scheduler.log

# conf

timelapse.conf

# file naming convention

- picture name
- video name
- nas name
- youtube name
- conf file - should it be conf.ini?

logs
	- automated_timelapse_run.log (timelapse logfile - change name to timelapse.log)
	- disk_check.log
	- manager.log
	- scheduler.log
	- todays_run.log - just todays output

programs
	- timelapse
	- disk_checker.py
	- manager.py
	- scheduler.py
	- set_up_cron.py


schedules
	- YYYYMMDD_{device_id}_schedule.txt (json?)

pics
	- YYYYMMDD_{device_id}_pics
		- YYYYMMDD_{device_id}_xxx.jpg

videos
	- YYYYMMDD_{device_id}_timelapse.mp4

on nas - pics and videos reside within directory of name {device_id}

device_id
	- pics
		- YYYYMMDD_{device_id}_pics
			- YYYYMMDD_{device_id}_xxx.jpg
			- YYYYMMDD_{device_id}_xxx.jpg
		- YYYYMMDD_{device_id}_pics
			- YYYYMMDD_{device_id}_xxx.jpg
			- YYYYMMDD_{device_id}_xxx.jpg
		...
	- videos  // or not in a directory? why in a directory?
		- YYYYMMDD_{device_id}_timelapse.mp4
		- YYYYMMDD_{device_id}_timelapse.mp4
	...
