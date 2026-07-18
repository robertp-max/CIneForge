# The Transfiguration — Five-Minute CineForge Project

This bundle adds a **planning-only** CineForge project for a 5:00 live-action biblical sequence. It does not enqueue rendering, call ComfyUI, download models, or bypass approval gates.

## Included

- 8 scenes / 40 subscenes, each 7–8 seconds.
- Exact planned duration: 300 seconds.
- Valid LTX planning frame counts: 169 or 193 (`8n+1`) at 24 fps.
- 6 user-supplied character identity boards, linked as draft character references (low-resolution previews bundled in `assets_preview.zip`; full originals supported at import).
- 8 user-supplied scene storyboard boards, imported as draft `art_direction_reference` planning assets and never assigned as shot starting images (low-resolution previews bundled in `assets_preview.zip`; full originals supported at import).
- 15 additional user-supplied art-direction images are incorporated through explicit palette/cloud/light restrictions in the prompts; their Ascension poses are prohibited.
- Timed non-diegetic narration.
- Per-shot image/video/negative prompts and continuity instructions.
- Required 2× final upscale route and deterministic post route.

## Hard creative rule

**This is the Transfiguration, not the Ascension.** Jesus remains physically present on the mountain summit. He does not fly upward, stand on clouds, rise into heaven, or disappear into the sky. Images that show those poses are used only for palette, cloud depth, facial light and scale.

## Import into CineForge

From the repository root, after configuring `.env` and creating/migrating the database:

```powershell
.\.venv\Scripts\python scripts\import_transfiguration_project.py --source-archive "C:\\path\\to\\transfiguration.zip"
```

When `--source-archive` is omitted, CineForge imports the small repository previews instead. Every selected full-resolution source file is checked against its recorded SHA-256 before storage.

Preview the import without database or asset writes:

```powershell
.\.venv\Scripts\python scripts\import_transfiguration_project.py --dry-run
```

The canonical machine-readable project is gzip-compressed and stored as text-safe `project_payload.json.gz.b64.part*` chunks. CSV manifests are gzip-compressed. The importer reconstructs and validates them directly.

The importer is idempotent by deterministic project/story/campaign IDs and asset SHA-256. Re-running updates the draft plan instead of creating duplicate projects.

## Safety state after import

- Story and all planning records remain `draft`.
- `allow_rendering` remains `false`.
- Character references and storyboard boards remain unapproved.
- `--repair-assets-only` verifies existing asset rows and managed SHA-256 values, and rehydrates only absent bytes from a matching verified archive without changing hierarchy, shots, prompts, settings, approvals, campaigns, or timeline records.
- Every video shot remains blocked until clean single-frame start images, identity references and required workflow/benchmark gates are approved.
- No direct ComfyUI `/prompt` submission is performed.

## Asset provenance

The images were supplied by the project owner. The repository contains 14 optimized planning previews (six identity boards and eight scene boards) plus a gzip-compressed SHA-256 inventory of the full 114-file supplied archive. Inclusion does not represent a model-release, identity-rights or third-party-license determination; the project owner remains responsible for production-use rights.
