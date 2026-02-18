# Implementation Phases

## Phase 0: Prerequisites

- [ ] Proxmox running
- [ ] NAS accessible with timelapse archive
- [ ] Basic Docker knowledge

## Phase 1: Local container development

Build the yearly-timelapse container locally first.

### Tasks

- [ ] Create Dockerfile with Python + OpenCV
- [ ] Write script: count folders, sample images, create video
- [ ] Test locally with mounted test data
- [ ] Verify output video is correct

### Deliverable

Working container that can be run with:

```bash
docker run -v /path/to/nas:/data timelapse-yearly
```

## Phase 2: k3s setup

### Tasks

- [ ] Create VM in Proxmox for k3s
- [ ] Install k3s single-node
- [ ] Verify kubectl works
- [ ] Set up NFS mount to NAS

### Deliverable

k3s cluster with NAS accessible as PersistentVolume

## Phase 3: Deploy first CronJob

### Tasks

- [ ] Push container image to registry (Docker Hub or local)
- [ ] Write CronJob manifest
- [ ] Deploy to k3s
- [ ] Verify it runs on schedule
- [ ] Check output appears on NAS

### Deliverable

Monthly timelapse job running automatically

## Phase 4: Observability

### Tasks

- [ ] Deploy Prometheus + Pushgateway to k3s
- [ ] Add metrics to container (duration, frames processed, success/fail)
- [ ] Push metrics at end of job
- [ ] Create basic Grafana dashboard
- [ ] Set up alert for failed jobs

### Deliverable

Can see job history and get alerts on failures

## Phase 5: Additional containers

### Tasks

- [ ] Build blur-timelapse container
- [ ] Build notifier container
- [ ] Deploy as CronJobs
- [ ] Add to observability

### Deliverable

Full container ecosystem running

## Phase 6: Polish

### Tasks

- [ ] Document everything
- [ ] Backup k3s config
- [ ] Consider GitOps (ArgoCD?) for manifest management
- [ ] Review and harden security

## Milestones

| Milestone | Definition of done |
|-----------|-------------------|
| M1 | Container runs locally, produces valid video |
| M2 | k3s running, can deploy pods |
| M3 | First CronJob runs automatically, output on NAS |
| M4 | Can see metrics in Grafana |
| M5 | All three containers deployed and working |

## Start here

Phase 1, Task 1: Create the Dockerfile.

Don't overthink it. Get something working, then iterate.
