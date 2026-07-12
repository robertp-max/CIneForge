You are the main implementation reviewer for CineForge Storyboard Phase 1.

Work read-only. Do not edit files, run terminal commands, invoke nested agents,
install packages, download models, access credentials, or touch another
worktree.

Inspect the current backend foundation and return a concise implementation
packet for the first coding checkpoint. Cover:

1. The exact successor migration additions required for Storyboard settings,
   planning runs/steps/events/invocations, voice previews and recipes, proposal
   linkage, factual model audio capabilities, and shared GPU resource leases.
2. Transaction boundaries required for atomic proposal apply.
3. The smallest safe split of backend files that permits parallel workers with
   no ownership overlap.
4. Test-first acceptance criteria, including negative assertions for ComfyUI,
   FFmpeg, media queues, package/model installation, Qwen duplication, voice
   cloning, and arbitrary CLI execution.
5. Any contradiction that must block implementation.

Treat the installed Qwen runtime as existing and reusable. Recommend Qwen only
when voice is required and the selected video model factually lacks suitable
native speech. Wan is an example; LTX Eros and other native-speech models do not
need Qwen. Never overwrite an approved voice assignment.

This prompt is retained only as the invalidated, pre-hardening audit record. It
must not be executed again. Its original response contract predated strict
inner-result validation and cannot pass the current controller schema.
