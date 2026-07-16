# Local Operator Live Boundary

Date: 2026-07-16

This document defines the explicit approval boundary for any local CineForge action that would touch live ComfyUI, GPU, FFmpeg/ffprobe, rendering, benchmarking, runtime health probes, queue execution, prompt submission, or media-tool execution.

## Non-approval phrases

The following are **not** live-run approvals:

- `ok`
- `k`
- `continue`
- `go on`
- `what's next`
- approval of a Storyboard or shot plan
- creation of `/local-operator/packets`
- viewing `/local-operator/runbooks`
- approving a voice/profile/asset/shot/storyboard planning record

These phrases/actions may authorize more offline planning or metadata work, but they do not authorize live runtime/media-tool execution.

## Required approval shape

A live approval must name all of the following:

1. **Action family**: M4 ComfyUI/GPU ladder, M5 FFmpeg/ffprobe probe validation, M5 FFmpeg assembly validation, or another exact family.
2. **Target**: archetype, recipe/template ID, packet ID, plan ID, stage number(s), or input/output manifest IDs.
3. **Scope**: one stage/run/recipe at a time unless a bounded serial range is explicitly listed.
4. **Local-only constraint**: no public/autonomous generation or internet-facing exposure.
5. **Acknowledgement of live tools**: explicitly states that ComfyUI/GPU/render/benchmark or FFmpeg/ffprobe work may run.

Example approval language:

> I approve a local M4 ComfyUI/GPU hardware probe for `CF-VID-01`, Stage 0 only, using the current M4 ladder and operator packet `<packet-id>`. Keep public/autonomous generation disabled.

Example M5 approval language:

> I approve a local M5 FFmpeg/ffprobe validation run for recipe `<template-id>` using plan `<plan-id>` only. Use allowlisted structured arguments, no raw command strings, and keep public/autonomous generation disabled.

## Required defaults before approval

Before any future live runner may start:

- Public raw `/prompt` remains absent.
- Public/autonomous generation remains disabled.
- Operator packet exists for the exact mode.
- Operator runbook has been reviewed.
- Paths, hashes, probes, workflow/model pins, and output roots are managed and recorded.
- GPU work has an exclusive lease path and queue-empty checks.
- FFmpeg/ffprobe work uses allowlisted structured recipe builders only.
- Stop rules and outcome/error persistence are understood.

## Stop conditions

Any future live run must stop and record error provenance if one of these occurs:

- approval scope mismatch,
- unsafe path or missing hash,
- unapproved graph/model/profile/stage/recipe,
- direct/raw ComfyUI prompt submission,
- raw FFmpeg command string,
- missing GPU lease for Comfy/GPU work,
- public/autonomous generation becomes enabled,
- OOM/crash/stale lease/non-empty queue after cleanup,
- output hash/probe cannot be captured when required.

## Current status

Current CineForge local surfaces are offline/read-only or manifest-only. They do not approve or run live work:

- `GET /local-operator/approval-templates`
- `GET /local-operator/approval-templates/{mode}`
- `GET /local-operator/runbooks`
- `POST /local-operator/packets`
- `GET /local-runtime/m4-preflight`
- `GET /local-runtime/m4-ladder`
- `GET /local-runtime/local-mvp-readiness`
- `GET /local-runtime/public-readiness`
- `GET /local-runtime/ffmpeg-recipes`
- `/local-generation/*` offline semantic manifests/handoffs
- `/local-post-production/*` offline/read-only manifests

No live FFmpeg, ffprobe, ComfyUI, GPU workload, render, benchmark, runtime health probe, queue execution, prompt submission, or public generation action is authorized by this document.
