# Learning Path: Containerisation

## Goal

Learn enough to deploy stateless containers on Proxmox that run scheduled tasks.

## Phase 1: Docker fundamentals

**Learn:**

- Dockerfile basics (FROM, COPY, RUN, CMD)
- Building images
- Running containers with volume mounts
- Understanding stateless design

**Practice project:**

Build a simple container that reads files from a mounted directory, does something, writes output. This mirrors the timelapse container pattern.

## Phase 2: Choose deployment path

### Option A: k3s (recommended to start)

- Lightweight Kubernetes
- CronJobs are built-in
- More transferable skills

**Learn:**

- k3s installation on Proxmox VM
- Pod basics
- CronJob resource
- PersistentVolumeClaims for NAS access

### Option B: Proxmox + Terraform

- More infrastructure-focused
- Direct container management

**Learn:**

- Proxmox LXC vs VM
- Terraform provider for Proxmox
- Terraform basics (resources, state, plan/apply)

## Phase 3: Observability

**Learn:**

- Prometheus basics
- Pushgateway (for short-lived containers that can't be scraped)
- Basic metrics (job duration, success/failure, files processed)

## Phase 4: NAS integration

**Learn:**

- NFS mounts in containers/k8s
- Volume permissions
- Read/write patterns for stateless jobs

## Suggested order

1. Docker → build the timelapse container locally
2. k3s → deploy it as a CronJob
3. NAS mount → connect to real data
4. Prometheus → add observability
5. Iterate → add more containers

## Resources to explore

- Your AnythingLLM books
- k3s docs: https://k3s.io
- Docker docs: https://docs.docker.com
