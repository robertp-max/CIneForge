# Workflow Template Manifest

Each workflow template contains:

- `workflow_api.json`: exported ComfyUI API workflow JSON.
- `workflow_manifest.json`: versioned semantic mapping from runtime parameters to workflow nodes and inputs.

Required manifest fields:

- `template_id`
- `version`
- `original_workflow_sha256`
- `comfyui_snapshot_ref`
- `nodes`

Each node reference contains:

- `node_id`
- `class_type`
- `input`
- `runtime_parameter`
- `value_schema`
- `required`

Validation rules:

- The workflow SHA256 must match the manifest.
- Every referenced node ID must exist.
- The node `class_type` must match the manifest.
- The referenced input must exist under node `inputs`.
- Runtime patch payload values must match the value schema.
- `output_prefix` is sanitized before patching.
- Optional object-info validation checks installed node classes and inputs without requiring live ComfyUI in tests.

Snapshot behavior:

- Patched workflow JSON is deep-copied from the template workflow.
- The patched workflow is written once to `storage/workflow_snapshots`.
- Existing snapshot paths are never overwritten.

