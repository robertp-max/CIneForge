# Queue State Machine

Active flow:

```text
pending -> reserved -> validating -> submitted -> running -> collecting_outputs -> complete
```

Failure states:

```text
validation_failed
comfy_rejected
runtime_failed
timeout
interrupted
oom
postprocess_failed
```

Documented extension:

```text
canceled
```

`canceled` is allowed only from `pending`, `reserved`, or `validating`, before a job is submitted to ComfyUI.

Rules:

- The backend queue is the source of truth, not ComfyUI's internal queue.
- A future queue worker must serialize GPU video generation.
- ComfyUI queue depth should remain shallow, ideally 0-1.
- Every transition returns an audit-event payload; Sprint 1B should persist that to `audit_logs`.
- AI proposals cannot mutate queue state.

