# Backup Algorithm

## When

We might check middle of night at shortest day of year for our geolocation?

Daily at 23:00 via `manager.py`

## Steps

1. rsync today's pics folder to NAS → `YYYYMMDD-[Device_ID]-timelapse_pics/`
2. rsync today's video to NAS → `YYYYMMDD-[Device_ID]-timelapse.mp4`
3. Create backup marker file to track what's been synced
4. Delete local files older than retention period (default 4 days, set in .conf)

## Notes

- Uses rsync daemon (no SSH keys required)
- Only deletes files that have been successfully backed up
- Pics are deleted before videos when disk space is low



## RSync for NAS

Back up 

## Youtube upload

Upload the oldest video first - incase of internet outage, to preserve order, to work within the six videos/day youtube API limit.

## Clean up device

if storage space is x, remove pics, then remove videos


## Fall back stratey

Critical points
- Google authorisation expires and we don't up load to Youtube - we have on NAS and we have on device
- NAS fills up

If a video is backed up to NAS & uploaded - can we delete it already?

Could we do this with a csv to monitor all these points? Date, sunrise, sunset, start, end, is it on nas? is it on youtube?

If video is not uploaded to YouTube → keep on device until it is.

## Asset lifecycle

Each day creates assets (pics folder, video file) that eventually must be deleted. We need to track:

- Where does each asset exist? (device, NAS, YouTube)
- Is it safe to delete from device?

Deletion rules:

- On NAS + YouTube → delete from device immediately
- On NAS only → keep on device for retention period
- On device only → never delete (no backup exists)

## Database vs simple tracking

A full database feels like overkill for this. Options:

1. **Marker files** - current approach, simple but limited
2. **CSV file** - single file tracking all days, easy to query
3. **SQLite** - lightweight DB, maybe overkill?

## Future idea: microservices architecture

Could be a secondary project. Each service would:

1. Check a location for work to do
2. Perform its action
3. Update a central database
4. Retire

Services: `nas-backup`, `youtube-upload`, `device-cleanup`, `nas-cleanup`

This decouples everything - each service only knows its own job
