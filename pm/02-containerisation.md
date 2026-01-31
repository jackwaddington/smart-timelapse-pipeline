# Containerisation & Proxmox Deployment

## Philosophy

Keep the current Pi Zero system as the "lone ranger" - a complete, self-contained device that does everything on its own. No dependencies, no network requirements beyond backup.

But we can extract principles from this project into stateless containers that come alive, do work, and disappear.

## Why containers?

Docker containers have no state. They:

1. Come alive
2. Do something
3. Disappear

Perfect for scheduled, discrete tasks.

## Container ideas

### Monthly: yearly timelapse generator

Runs once a month. Creates a "year in review" timelapse from NAS archives.

Steps:

1. Look in NAS, count number of day-folders
2. Calculate frames needed for 30 sec video (~750 frames at 25fps)
3. Divide days by 750 to get sampling rate
4. Copy one pic from each sampled day into container
5. Process into 30 second timelapse
6. Write to NAS in `yearly-timelapse/` directory
7. Report metrics to Prometheus
8. Die

### Daily: notifier / uploader

Runs once a day. Checks for new content.

- Check if new file exists in a directory
- Notify me (email? webhook?)
- Or auto-upload to YouTube

Concern: YouTube OAuth tokens might expire if used infrequently. May need token refresh strategy.

### Monthly: blur filter timelapse

Create a more visual version - blur all images to show just light and colour changes over the year. Abstract colours from data.

## Deployment options

### Terraform + Proxmox

Automate container lifecycle with Terraform. Define infrastructure as code.

### k3s

Lightweight Kubernetes. CronJobs would handle the scheduling natively.

## Things to learn

- Docker containerisation
- Proxmox API
- Terraform basics
- k3s / Kubernetes CronJobs
- Prometheus metrics from short-lived containers
