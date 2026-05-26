# Contributing

## Project Phase

CineForge is currently in Sprint 1A foundation work. Contributions should preserve the architecture boundaries in the research packet and must not introduce real generation, model downloads, ComfyUI mutation, autonomous execution, or parallel GPU generation.

## Local Checks

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
.\.venv\Scripts\python -m pytest
```

## Development Rules

- Keep ComfyUI external and isolated.
- Keep the backend as the source of truth for queue state.
- Preserve the one-GPU-worker rule for future generation.
- Validate workflow changes through manifests.
- Do not allow AI proposal code to mutate workflows, queues, DB records, assets, registries, ComfyUI submissions, or FFmpeg commands.
- Do not commit generated media, local DB files, model files, or secrets.

## Pull Requests

Include:

- Scope summary.
- Tests run.
- Architecture docs referenced.
- Any deferred work or known gaps.

