# Workflow JSON Mutation Strategy

ComfyUI API workflows are exported with top-level node IDs. The backend must patch runtime fields deterministically while preserving an immutable run snapshot.

## Node Identification Strategy

1. Export workflow using ComfyUI dev mode `Save (API format)` / `Export (API)` and retain the pinned UI workflow when API JSON does not preserve titles.
2. Build a separate manifest mapping semantic bindings to graph SHA, node class, unique semantic title, input name, and resolved API node ID.
3. Validate each mapped node by graph hash, `class_type`, unique title, resolved node ID, and input name before submission.
4. Use `GET /object_info` to validate installed node classes and field availability.
5. Snapshot patched workflow JSON per run.

Avoid relying on UI node position, title alone, or numeric ID alone. Numeric IDs are execution details stored only after title/class/input admission against an immutable graph hash.

## Runtime Parameter Matrix

| Runtime Parameter | Node Type / Search Strategy | Field to Mutate | Validation Rule | Database Field |
|---|---|---|---|---|
| Positive prompt | Manifest semantic key; text encode node class varies | `inputs.text` or implementation-specific prompt field | Non-empty string | `prompts.text` |
| Negative prompt | Manifest semantic key | `inputs.text` | String, can be empty if workflow supports | `negative_prompts.text` |
| Seed | Sampler/noise node from manifest | `inputs.seed` / `noise_seed` | Integer 0 to max supported | `clip_iterations.seed` |
| Width | Latent/video size node | `inputs.width` | Divisible by model requirement, usually 32 | `clip_iterations.width` |
| Height | Latent/video size node | `inputs.height` | Divisible by model requirement, usually 32 | `clip_iterations.height` |
| Frame count | Video latent/image sequence node | `inputs.length`, `frames`, or workflow-specific | Valid for model family; local validation | `clip_iterations.frame_count` |
| FPS | VHS/save/video node or metadata field | `inputs.frame_rate` / `fps` | Positive integer | `clip_iterations.fps` |
| Steps | Sampler node | `inputs.steps` | Preset range | `clip_iterations.steps` |
| Sampler | Sampler node | `inputs.sampler_name` | Must appear in object_info options | `clip_iterations.sampler` |
| Scheduler | Sampler node | `inputs.scheduler` | Must appear in object_info options | `clip_iterations.scheduler` |
| CFG/guidance | Sampler/guidance node | `inputs.cfg`, `guidance`, or node-specific | Numeric range per workflow | `clip_iterations.guidance` |
| STG / skip-layer guidance | LTX/Wan-specific guidance node if present | Implementation-specific | Only mutate if node exists | `clip_iterations.extra_params` |
| Model checkpoint | Loader node | `inputs.ckpt_name` or diffusion model name | File exists in expected folder | `model_variants.file_path` |
| Text encoder | Text encoder loader | `inputs.clip_name` / encoder filename | File exists and hash matches registry | `text_encoders.id` |
| VAE | VAE loader | `inputs.vae_name` | File exists and hash matches registry | `vaes.id` |
| Quant loader | Loader class itself may differ | Loader-specific model filename | Loader present in object_info | `quantizations.id` |
| LoRA list | LoRA loader chain or stack node | Loader-specific fields | Ordered list, compatible base verified | `lora_combinations.id` |
| LoRA strengths | LoRA loader chain | `strength_model`, `strength_clip`, or implementation-specific | Numeric range; preserve order | `lora_combination_items` |
| Image input path | Load image/video node | `image`, `video`, `path` | Uploaded/accessible path exists | `generated_assets.input_asset_id` |
| Conditioning image path | I2V/control node | Implementation-specific | Path exists | `clip_iterations.conditioning_asset_id` |
| Output filename prefix | Save node | `inputs.filename_prefix` | Controller-built as `<project-folder>/<run-stem>`; both components sanitized; absolute paths, traversal, drive prefixes, backslashes, and deeper trees rejected | local run manifest `output_prefix` |
| Save path | Save node if supported | Implementation-specific | Do not expose to user input; if used, must remain inside `CINEFORGE_COMFYUI_OUTPUT_ROOT` | local run manifest `output_path` |

## Template Manifest Example

```json
{
  "template_id": "ltx23-distilled-single-stage-v001",
  "model_key": "ltx2_3_22b_distilled_1_1_fp8",
  "api_graph_sha256": "recorded-at-admission",
  "ui_graph_sha256": "recorded-at-admission-if-needed-for-titles",
  "comfyui_commit": "recorded-at-install",
  "nodes": {
    "positive_prompt": {
      "node_id": "resolved-api-node-id",
      "semantic_title": "CF Positive Prompt",
      "class_type": "example-class-from-admitted-graph",
      "input": "text"
    },
    "seed": {
      "node_id": "resolved-api-node-id",
      "semantic_title": "CF Seed",
      "class_type": "example-class-from-admitted-graph",
      "input": "seed"
    },
    "output_prefix": {
      "node_id": "resolved-api-node-id",
      "semantic_title": "CF Output Prefix",
      "class_type": "example-class-from-admitted-graph",
      "input": "filename_prefix",
      "value_example": "Project_A/run_0001"
    }
  }
}
```

Class names above are examples only. The real manifest must be generated from the exported workflow and verified with the installed node set.

## TypeScript Patch Pseudo-Code

```ts
type NodeRef = { node_id: string; class_type: string; input: string };
type Workflow = Record<string, { class_type: string; inputs: Record<string, unknown> }>;

function patchInput(workflow: Workflow, ref: NodeRef, value: unknown) {
  const node = workflow[ref.node_id];
  if (!node) throw new Error(`Missing node ${ref.node_id}`);
  if (node.class_type !== ref.class_type) {
    throw new Error(`Node ${ref.node_id} class changed: expected ${ref.class_type}, got ${node.class_type}`);
  }
  if (!(ref.input in node.inputs)) {
    throw new Error(`Node ${ref.node_id} missing input ${ref.input}`);
  }
  node.inputs[ref.input] = value;
}
```

## Reproducibility Rule

Every local run manifest stores:

- Template ID and template version.
- Original template SHA256.
- Patched workflow JSON.
- Patch payload JSON.
- ComfyUI commit and custom node snapshot.
- Model/LoRA/text encoder/VAE file hashes.
- ComfyUI `prompt_id`.
- Project output folder under `CINEFORGE_COMFYUI_OUTPUT_ROOT`.
- Final output paths relative to the project output folder.
