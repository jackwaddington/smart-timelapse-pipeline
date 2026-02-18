# Architecture: Containerised Timelapse System

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         PROXMOX HOST                            │
│                                                                 │
│  ┌─────────────┐    ┌─────────────────────────────────────┐    │
│  │   k3s VM    │    │              NAS                    │    │
│  │             │    │                                     │    │
│  │  CronJobs:  │───▶│  /timelapse-archive/                │    │
│  │  - monthly  │◀───│    ├── 20240101-device1/            │    │
│  │  - daily    │    │    ├── 20240102-device1/            │    │
│  │  - blur     │    │    └── yearly-timelapse/            │    │
│  │             │    │                                     │    │
│  └──────┬──────┘    └─────────────────────────────────────┘    │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐                                               │
│  │ Prometheus  │                                               │
│  │ + Grafana   │                                               │
│  └─────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘

         ▲
         │ (independent)
         │
┌────────┴────────┐
│  Pi Zero        │
│  "Lone Ranger"  │
│                 │
│  Daily capture  │───rsync───▶ NAS
│  Local backup   │
└─────────────────┘
```

## Components

### Pi Zero (existing)

- Unchanged from current design
- Captures daily, creates videos, rsyncs to NAS
- Completely independent - no dependency on Proxmox system

### NAS

- Central storage for all timelapse data
- Mounted as NFS volume in k3s
- Structure:

```
/timelapse-archive/
├── [DEVICE_ID]/
│   ├── 20240101-timelapse_pics/
│   ├── 20240101-timelapse.mp4
│   ├── 20240102-timelapse_pics/
│   └── ...
├── yearly-timelapse/
│   └── 2024-yearly.mp4
└── blur-timelapse/
    └── 2024-blur.mp4
```

### k3s cluster

Single node to start. Runs CronJobs:

| Job | Schedule | Input | Output |
|-----|----------|-------|--------|
| yearly-timelapse | Monthly | Day folders | yearly-timelapse/ |
| blur-timelapse | Monthly | Day folders | blur-timelapse/ |
| notifier | Daily | New files | Notification |

### Prometheus + Pushgateway

- Pushgateway receives metrics from short-lived containers
- Prometheus scrapes Pushgateway
- Grafana for dashboards

## Data flow

### Monthly timelapse job

```
1. CronJob triggers
2. Container starts
3. Mounts NAS via NFS
4. Reads day-folders, samples images
5. Processes video (OpenCV)
6. Writes to yearly-timelapse/
7. Pushes metrics to Pushgateway
8. Container terminates
```

### Daily notifier job

```
1. CronJob triggers
2. Container starts
3. Checks for new files since last run
4. Sends notification (webhook/email)
5. Pushes metrics
6. Container terminates
```

## Secrets management

- YouTube OAuth tokens (if used)
- Notification webhook URLs
- NAS credentials (if not using NFS)

Options: Kubernetes Secrets, external secret manager

## Failure handling

- Jobs are idempotent - can re-run safely
- Failed jobs logged in Prometheus
- Alert on consecutive failures
