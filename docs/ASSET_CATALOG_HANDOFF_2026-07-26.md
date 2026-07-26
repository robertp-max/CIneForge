# Local Asset Catalog — Implementation Handoff

**Date:** 2026-07-26
**Plan:** `docs/ASSET_CATALOG_IMPLEMENTATION_PLAN_2026-07-25.md`

## What works now

### Database
- Table `local_runtime_assets` (Alembic `g4a5b6c7d8e9`)
- Presence-driven catalog; no approval/licensing gates

### Sync CLI
```powershell
.venv\Scripts\python.exe scripts\sync_local_comfy_assets.py `
  --comfyui-root C:\AI\ComfyUI_windows_portable\ComfyUI `
  --skip-hash
```
- First real sync result: **122 present assets**, ~478 GB catalogued, 0 errors
- Types: 13 checkpoints, 55 LoRAs, 36 workflows (json/png/zip), plus VAE/TE/etc.

### API (`/runtime-catalog/...`)
| Method | Path |
|--------|------|
| GET | `/local-assets` |
| GET | `/local-assets/summary` |
| GET | `/local-assets/{id}` |
| GET | `/checkpoints` |
| GET | `/local-loras` |
| GET | `/local-workflows` |
| POST | `/sync` |

### Frontend
- Studio nav: **Local assets** → `/projects/{id}/studio/local-assets`
- Page: tables, search, family filter, metadata drawer, multi-LoRA stack editor, selection JSON for generation requests

### Resolver
- `backend.app.services.local_assets.resolver.resolve_generation_assets`
- Raises clear `AssetResolutionError` on missing/wrong-type/not-on-disk

### Tests
```text
backend/tests/test_local_runtime_assets.py — 6 passed
```

## Not fully finished (follow-ups)

| Item | Status |
|------|--------|
| Phase 6 image generation fully rewritten onto asset IDs | Schema + resolver ready; Phase 6 service still uses prior paths — wire `LocalGenerationAssetSelection` into Phase 6 request body next |
| Generic workflow graph parameter patcher | Deferred — community AIO remains selectable; execution still needs graph-specific patch maps (plan agents A36/A43–A45) |
| Streaming SHA on multi-GB files | Supported (`compute_hash=True`); UI/sync defaults skip hash for speed; re-run without `--skip-hash` or with `--hash-max-bytes` for selective hashing |
| Duplicate cleanup on disk | Catalog reports duplicates by hash when hashed; never deletes files |

## Key files

| Area | Path |
|------|------|
| ORM | `backend/app/db/base.py` (`LocalRuntimeAsset`) |
| Migration | `backend/alembic/versions/g4a5b6c7d8e9_add_local_runtime_assets.py` |
| Scanner / meta / sync | `backend/app/services/local_assets/` |
| Routes | `backend/app/api/routes/runtime_catalog.py` |
| CLI | `scripts/sync_local_comfy_assets.py` |
| UI | `frontend/src/studio/pages/LocalAssetsPage.tsx` |
| Sync summary sample | `artifacts/local_asset_sync_summary.json` |

## Operator notes

1. Run migration: `alembic upgrade head`
2. Sync assets after adding files to ComfyUI
3. Checkpoints remain under `models/checkpoints` only (including diffusion weights co-located there)
4. All local assets stay visible and selectable regardless of review state
