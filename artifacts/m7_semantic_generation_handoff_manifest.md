# M7 Semantic Generation Handoff Manifest Artifact

Implemented local/offline semantic generation request manifests at `/local-generation/semantic-requests`.

Safety contract:
- Persists sanitized `SemanticGenerationRequest` payloads under `storage_root/local_generation/semantic_requests`.
- Sanitizes `output_prefix` with the ComfyUI filename-prefix rules before gate evaluation, workflow compilation, manifest persistence, or audit append.
- Rejects absolute paths, traversal, backslashes, drive-like components, and deeper-than-`project/run` prefixes.
- Keeps manifest and audit paths inside `storage_root/local_generation/semantic_requests`.
- Persists `ProductionGateService.evaluate_generation_request` reports with blocking reasons.
- Defaults current blocked evidence to `state=blocked_by_gates` and never compiles when gates block.
- If gates allow in future evidence, snapshots compiled workflow metadata offline only using the sanitized request.
- Always records `generation_submitted=false`, `comfy_prompt_id=null`, and `queue_job_id=null`.
- The Jobs page now includes a clearly labeled offline semantic request manifest form using bounded CF-PRESET-001 / CF-VID-01 draft t2v defaults and a read-only manifest table.
- No ComfyUI submission, queue/DB job creation, GPU leases, runtime health calls, probes, FFmpeg, benchmark, or render execution are part of the path.
