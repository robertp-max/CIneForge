# Storyboard Phase A Specification

Phase A supports planning CRUD, ordering, narration planning, prompt packages, model/workflow recommendations, provider routing records, readiness, immutable storyboard versions, and JSON/CSV exports. It ends at human approval of a production plan.

Shots must be positive and normally 6–12 seconds. An out-of-range shot requires a non-empty override reason. Story planned duration is calculated from active shots and must equal the Story target before approval. Every shot needs narration or a documented exception.

Approval records an immutable snapshot and an audit event. It never creates a ComfyUI submission, queue job, GPU workload, FFmpeg job, model download, voice clone, Timeline Slot, or Clip Iteration.
