# Storyboard Readiness Gates

The backend is authoritative. It calculates hierarchy duration rollups, target-duration discrepancy, missing narration, and explicitly blocked shots. Approval returns HTTP 409 until blockers clear. Frontend readiness displays mirror this response rather than localStorage or mock values.

Registry, ComfyUI, GPU, benchmark, workflow, and provider availability are Unknown/Unverified/Not Configured unless a real backend source supplies evidence. No UI should claim installed models, safe 1080p generation, connected providers, or render estimates without that evidence.
