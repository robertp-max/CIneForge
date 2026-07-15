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

## UI-format admission candidate

`storage/workflow_templates/cf_vid_01_ltx23_single_stage/` stores the local ComfyUI-LTXVideo LTX-2.3 single-stage example as `workflow_ui.json` plus `workflow_ui_manifest.json`.

The UI candidate is retained as source evidence:

- It validates UI graph SHA, node class, widget index, selected model checkpoint patch points, and safe output-prefix widget bindings.
- It writes immutable `.ui.json` snapshots for UI-level audit if needed.

## CF-VID-01 API smoke template

`storage/workflow_templates/cf_vid_01_ltx23_single_stage/workflow_api.json` and `workflow_manifest.json` define `cf_vid_01_ltx23_single_stage_t2v_smoke`.

Runtime evidence on 2026-07-13:

- `/object_info` passed for all required classes after installing RES4LYF.
- Two serialized T2V smoke jobs succeeded with selected `ltx-2.3-22b-distilled-1.1-fp8.safetensors`.
- Outputs and hashes are recorded in `docs/CFVID01_RUNTIME_SMOKE.md`.

The template remains benchmark-gated. It is a T2V smoke candidate, not full preset/profile readiness.

